from __future__ import annotations

from dataclasses import replace
from datetime import date
import re
import unicodedata

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.keyboards.decision import answer_with_decision_keyboard, save_cancel_keyboard
from bot.handlers.start import build_start_status_message
from bot.services.decision_resolver import resolve_yes_no
from bot.services.invoice_service import InvoiceService
from bot.services.workspace_invoice_service import WorkspaceInvoiceService
from bot.services.workspace_context import WorkspaceContext, WorkspaceContextError, WorkspaceContextService
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)
from bot.services.semantic_action_resolver import resolve_semantic_action
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


SUPPLIER_ONBOARDING_SAVED_NEXT_STEP_MESSAGE = (
    'Profil dodávateľa bol uložený.\n\n'
    'Ďalší krok: vytvorte si prvú službu cez /sluzbu.\n'
    'Služba je krátky názov, ktorý bot neskôr použije pri faktúre a PDF.'
)
ONBOARDING_RECOVERY_HINT = (
    'Ak chcete onboarding ukončiť, napíšte „zrušiť“. Ak chcete začať odznova, použite /start.'
)


def _with_onboarding_recovery_hint(message: str) -> str:
    return f'{message}\n\n{ONBOARDING_RECOVERY_HINT}'


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
    waiting_activation_confirm = State()


class SupplierProfileEditStates(StatesGroup):
    field = State()
    value = State()
    confirm = State()


_ONBOARDING_MODE_KEY = 'supplier_onboarding_mode'
_ONBOARDING_WORKSPACE_ID_KEY = 'supplier_onboarding_workspace_id'
_SUPPLIER_EDIT_WORKSPACE_ID_KEY = 'supplier_edit_workspace_id'

_SUPPLIER_EDIT_FIELD_LABELS = {
    'name': 'názov',
    'ico': 'ICO',
    'dic': 'DIC',
    'ic_dph': 'IC DPH',
    'address': 'adresa',
    'iban': 'IBAN',
    'swift': 'SWIFT/BIC',
    'email': 'email',
    'days_due': 'splatnosť',
}

_SUPPLIER_EDIT_ALIASES = {
    'nazov': 'name',
    'meno': 'name',
    'firma': 'name',
    'obchodne meno': 'name',
    'ico': 'ico',
    'dic': 'dic',
    'ic dph': 'ic_dph',
    'icdph': 'ic_dph',
    'dph': 'ic_dph',
    'adresa': 'address',
    'address': 'address',
    'posta': 'address',
    'postova adresa': 'address',
    'iban': 'iban',
    'swift': 'swift',
    'bic': 'swift',
    'swift bic': 'swift',
    'email': 'email',
    'mail': 'email',
    'splatnost': 'days_due',
    'dni splatnosti': 'days_due',
}


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


def _supplier_profile_summary(profile: SupplierProfile) -> str:
    return (
        '<b>Profil dodávateľa</b>\n\n'
        f'• Názov: {profile.name}\n'
        f'• ICO: {profile.ico}\n'
        f'• DIC: {profile.dic}\n'
        f'• IC DPH: {profile.ic_dph or "-"}\n'
        f'• Adresa: {profile.address}\n'
        f'• IBAN: {profile.iban}\n'
        f'• SWIFT: {profile.swift}\n'
        f'• Email: {profile.email}\n'
        f'• Splatnosť: {profile.days_due} dní\n\n'
        'Ak potrebujete zmeniť jeden údaj, použite /upravit_profil.\n'
        'Ďalší krok pre fakturáciu: /sluzbu.'
    )


def _normalize_choice(value: str) -> str:
    text = value.strip().lower().replace('_', ' ')
    normalized = unicodedata.normalize('NFKD', text)
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_diacritics).strip()


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


def _edit_field_options_text() -> str:
    options = ', '.join(_SUPPLIER_EDIT_FIELD_LABELS.values())
    return f'Ktorý údaj chcete zmeniť? Možnosti: {options}.'


def _resolve_supplier_edit_field_fast_path(user_text: str) -> str | None:
    normalized = _normalize_choice(user_text)
    exact = _SUPPLIER_EDIT_ALIASES.get(normalized)
    if exact is not None:
        return exact

    matched_fields: set[str] = set()
    for alias, field in _SUPPLIER_EDIT_ALIASES.items():
        if re.search(rf'\b{re.escape(alias)}\b', normalized):
            matched_fields.add(field)

    if len(matched_fields) == 1:
        return next(iter(matched_fields))
    return None


async def _resolve_supplier_edit_field(user_text: str, config: Config) -> str | None:
    fast_path = _resolve_supplier_edit_field_fast_path(user_text)
    if fast_path is not None:
        return fast_path

    canonical = await resolve_semantic_action(
        context_name='supplier_profile_edit_field',
        allowed_actions=[*_SUPPLIER_EDIT_FIELD_LABELS.keys(), 'unknown'],
        user_input_text=user_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        action_hints={
            'name': {'meaning': 'supplier company or business name'},
            'ico': {'meaning': 'Slovak company ICO identifier'},
            'dic': {'meaning': 'Slovak tax DIC identifier'},
            'ic_dph': {'meaning': 'VAT ID / IC DPH field'},
            'address': {'meaning': 'supplier company address'},
            'iban': {'meaning': 'bank account IBAN for invoice payments'},
            'swift': {'meaning': 'bank SWIFT or BIC code'},
            'email': {'meaning': 'supplier email address'},
            'days_due': {'meaning': 'default invoice due-days / splatnost'},
        },
    )
    if canonical in _SUPPLIER_EDIT_FIELD_LABELS:
        return canonical
    return None


def _validate_supplier_edit_value(field: str, raw_value: str) -> tuple[bool, object, str | None]:
    value = raw_value.strip()
    if field == 'name':
        return (bool(value), value, 'Názov nemôže byť prázdny.')
    if field == 'ico':
        normalized = value.replace(' ', '')
        return (validate_ico(normalized), normalized, 'Neplatné ICO. Formát: 8 číslic.')
    if field == 'dic':
        normalized = value.replace(' ', '')
        return (validate_dic(normalized), normalized, 'Neplatné DIC. Formát: 10 číslic.')
    if field == 'ic_dph':
        if value == '-':
            return True, None, None
        normalized = value.upper().replace(' ', '')
        return (validate_ic_dph(normalized), normalized, 'Neplatné IC DPH. Príklad: SK1234567890.')
    if field == 'address':
        return (bool(value), value, 'Adresa nemôže byť prázdna.')
    if field == 'iban':
        normalized = value.upper().replace(' ', '')
        return (validate_iban(normalized), normalized, 'Neplatný IBAN.')
    if field == 'swift':
        return (bool(value), value.upper(), 'SWIFT/BIC nemôže byť prázdny.')
    if field == 'email':
        return (validate_email(value), value, 'Neplatný email.')
    if field == 'days_due':
        return (validate_days_due(value), int(value), 'Neplatná hodnota. Zadajte celé číslo > 0.')
    return False, value, 'Neznámy údaj.'


def _profile_value(profile: SupplierProfile, field: str) -> object:
    return getattr(profile, field)


def _with_profile_value(profile: SupplierProfile, field: str, value: object) -> SupplierProfile:
    return replace(profile, **{field: value})


def _active_workspace_context(config: Config, telegram_id: int) -> WorkspaceContext | None:
    if not config.db_path.exists():
        return None
    try:
        return WorkspaceContextService(config.db_path).resolve_for_user(telegram_id)
    except WorkspaceContextError as workspace_error:
        try:
            supplier = SupplierService(config.db_path).get_by_telegram_id(telegram_id)
        except RuntimeError:
            raise workspace_error
        if supplier is None or supplier.workspace_id is None:
            return None
        raise workspace_error


async def _start_supplier_onboarding(
    message: Message,
    state: FSMContext,
    *,
    mode: str = 'legacy',
    workspace_id: str | None = None,
) -> None:
    await state.clear()
    if hasattr(state, 'update_data'):
        await state.update_data(
            **{
                _ONBOARDING_MODE_KEY: mode,
                _ONBOARDING_WORKSPACE_ID_KEY: workspace_id or '',
            }
        )
    await state.set_state(OnboardingStates.name)
    await message.answer('1/10 Zadajte názov firmy / obchodné meno:')


async def start_additional_supplier_profile_onboarding(
    message: Message,
    state: FSMContext,
) -> None:
    await _start_supplier_onboarding(
        message,
        state,
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    )


@router.message(Command('moj_profil'))
async def cmd_moj_profil(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    try:
        context = _active_workspace_context(config, message.from_user.id)
    except WorkspaceContextError:
        await message.answer('Vyberte aktívny business profil cez /profily.')
        return
    supplier = (
        SupplierService(config.db_path).get_by_workspace_id(context.workspace_id)
        if context is not None
        else SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    )
    if supplier is None:
        await message.answer('Profil dodávateľa ešte nie je nastavený. Spúšťam vytvorenie profilu.')
        await _start_supplier_onboarding(
            message,
            state,
            mode=CREATE_FIRST_WORKSPACE_PROFILE if context is None else 'legacy',
        )
        return

    await state.clear()
    await message.answer(_supplier_profile_summary(supplier))


@router.message(lambda message: _is_case_variant_command(message.text or '', '/moj_profil'))
async def cmd_moj_profil_case_alias(message: Message, state: FSMContext, config: Config) -> None:
    await cmd_moj_profil(message, state, config)


@router.message(Command('upravit_profil'))
async def cmd_upravit_profil(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    try:
        context = _active_workspace_context(config, message.from_user.id)
    except WorkspaceContextError:
        await message.answer('Vyberte aktívny business profil cez /profily.')
        return
    supplier = (
        SupplierService(config.db_path).get_by_workspace_id(context.workspace_id)
        if context is not None
        else SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    )
    if supplier is None:
        await message.answer('Profil dodávateľa ešte nie je nastavený. Najprv spustite /moj_profil.')
        return

    await state.clear()
    await state.update_data(
        **{_SUPPLIER_EDIT_WORKSPACE_ID_KEY: context.workspace_id if context is not None else ''}
    )
    await state.set_state(SupplierProfileEditStates.field)
    await message.answer(_edit_field_options_text())


@router.message(lambda message: _is_case_variant_command(message.text or '', '/upravit_profil'))
async def cmd_upravit_profil_case_alias(message: Message, state: FSMContext, config: Config) -> None:
    await cmd_upravit_profil(message, state, config)


@router.message(SupplierProfileEditStates.field)
async def supplier_profile_edit_field(message: Message, state: FSMContext, config: Config) -> None:
    field = await _resolve_supplier_edit_field(message.text or '', config)
    if field is None:
        await message.answer(_edit_field_options_text())
        return

    await state.update_data(supplier_edit_field=field)
    await state.set_state(SupplierProfileEditStates.value)
    await message.answer(f'Zadajte novú hodnotu pre {_SUPPLIER_EDIT_FIELD_LABELS[field]}:')


@router.message(SupplierProfileEditStates.value)
async def supplier_profile_edit_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = str(data.get('supplier_edit_field') or '')
    ok, normalized_value, error = _validate_supplier_edit_value(field, message.text or '')
    if not ok:
        await message.answer(f'{error} Skúste znova:')
        return

    await state.update_data(supplier_edit_value=normalized_value)
    await state.set_state(SupplierProfileEditStates.confirm)
    label = _SUPPLIER_EDIT_FIELD_LABELS[field]
    display_value = normalized_value if normalized_value is not None else '-'
    await answer_with_decision_keyboard(
        message,
        f'Zmeniť {label} na: {display_value}?\n'
        'Zmenu treba potvrdiť.',
        save_cancel_keyboard(save_label='Uložiť zmenu'),
    )


@router.message(SupplierProfileEditStates.confirm)
async def supplier_profile_edit_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    if canonical_decision is None:
        answer = await resolve_yes_no(
            context_name='supplier_profile_edit_confirm',
            user_input_text=(message.text or ''),
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    else:
        answer = canonical_decision if canonical_decision in {'yes', 'no', 'unknown'} else 'unknown'
    if answer == 'unknown':
        await message.answer('Napíšte ano alebo nie.')
        return

    if answer == 'no':
        await state.clear()
        await message.answer('Úprava profilu bola zrušená.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    field = str(data.get('supplier_edit_field') or '')
    value = data.get('supplier_edit_value')
    service = SupplierService(config.db_path)
    workspace_id = str(data.get(_SUPPLIER_EDIT_WORKSPACE_ID_KEY) or '').strip()
    if workspace_id:
        try:
            WorkspaceContextService(config.db_path).require_membership(
                message.from_user.id,
                workspace_id,
            )
        except WorkspaceContextError:
            await state.clear()
            await message.answer('Business profil tejto úpravy už nie je dostupný.')
            return
        supplier = service.get_by_workspace_id(workspace_id)
    else:
        supplier = service.get_by_telegram_id(message.from_user.id)
    if supplier is None or field not in _SUPPLIER_EDIT_FIELD_LABELS:
        await state.clear()
        await message.answer('Profil dodávateľa sa nepodarilo nájsť. Spustite /moj_profil.')
        return

    previous = _profile_value(supplier, field)
    service.update_profile(_with_profile_value(supplier, field, value))
    await state.clear()
    previous_display = previous if previous is not None else '-'
    value_display = value if value is not None else '-'
    await message.answer(
        f'Profil bol aktualizovaný: {_SUPPLIER_EDIT_FIELD_LABELS[field]} '
        f'{previous_display} → {value_display}.\n\n'
        f'{build_start_status_message(config, message.from_user.id)}'
    )


@router.message(Command('onboarding', 'supplier'))
async def cmd_onboarding(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    service = SupplierService(config.db_path)
    try:
        context = _active_workspace_context(config, message.from_user.id)
    except WorkspaceContextError:
        await message.answer('Vyberte aktívny business profil cez /profily.')
        return
    existing = (
        service.get_by_workspace_id(context.workspace_id)
        if context is not None
        else service.get_by_telegram_id(message.from_user.id)
    )

    if existing:
        await message.answer(
            'Profil dodávateľa už existuje.\n'
            f'Aktuálny profil: {existing.name} ({existing.ico}).\n'
            'Onboarding teraz prejdeme znova kvôli aktualizácii.'
        )
        mode = 'update_workspace' if context is not None else 'legacy'
    else:
        await message.answer('Spúšťam onboarding dodávateľa.')
        mode = CREATE_FIRST_WORKSPACE_PROFILE

    await _start_supplier_onboarding(
        message,
        state,
        mode=mode,
        workspace_id=context.workspace_id if context is not None else None,
    )

@router.message(OnboardingStates.name)
async def onboarding_name(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer(_with_onboarding_recovery_hint('Názov nemôže byť prázdny. Skúste znova:'))
        return
    await state.update_data(name=value)
    await state.set_state(OnboardingStates.ico)
    await message.answer('2/10 Zadajte ICO (8 číslic):')


@router.message(OnboardingStates.ico)
async def onboarding_ico(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_ico(value):
        await message.answer(_with_onboarding_recovery_hint('Neplatné ICO. Formát: 8 číslic. Skúste znova:'))
        return
    await state.update_data(ico=value)
    await state.set_state(OnboardingStates.dic)
    await message.answer('3/10 Zadajte DIC (10 číslic):')


@router.message(OnboardingStates.dic)
async def onboarding_dic(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer(_with_onboarding_recovery_hint('Neplatné DIC. Formát: 10 číslic. Skúste znova:'))
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
            await message.answer(
                _with_onboarding_recovery_hint('Neplatné IC DPH. Príklad: SK1234567890. Skúste znova:')
            )
            return
        await state.update_data(ic_dph=value.upper().replace(' ', ''))

    await state.set_state(OnboardingStates.address)
    await message.answer('5/10 Zadajte adresu:')


@router.message(OnboardingStates.address)
async def onboarding_address(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer(_with_onboarding_recovery_hint('Adresa nemôže byť prázdna. Skúste znova:'))
        return
    await state.update_data(address=value)
    await state.set_state(OnboardingStates.iban)
    await message.answer('6/10 Zadajte IBAN:')


@router.message(OnboardingStates.iban)
async def onboarding_iban(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_iban(value):
        await message.answer(_with_onboarding_recovery_hint('Neplatný IBAN. Skúste znova:'))
        return
    await state.update_data(iban=value.upper().replace(' ', ''))
    await state.set_state(OnboardingStates.swift)
    await message.answer('7/10 Zadajte SWIFT/BIC:')


@router.message(OnboardingStates.swift)
async def onboarding_swift(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer(_with_onboarding_recovery_hint('SWIFT/BIC nemôže byť prázdny. Skúste znova:'))
        return
    await state.update_data(swift=value.upper())
    await state.set_state(OnboardingStates.email)
    await message.answer('8/10 Zadajte email:')


@router.message(OnboardingStates.email)
async def onboarding_email(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_email(value):
        await message.answer(_with_onboarding_recovery_hint('Neplatný email. Skúste znova:'))
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
            _with_onboarding_recovery_hint(
                f'Neplatné číslo faktúry. Zadajte číslo vo formáte {issue_year}NNNN, '
                f'napríklad {issue_year}0001:'
            )
        )
        return
    await state.update_data(first_invoice_number=value)
    await state.set_state(OnboardingStates.days_due)
    await message.answer('10/10 Zadajte štandardnú splatnosť v dňoch (celé číslo > 0):')


@router.message(OnboardingStates.days_due)
async def onboarding_days_due(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_days_due(value):
        await message.answer(_with_onboarding_recovery_hint('Neplatná hodnota. Zadajte celé číslo > 0:'))
        return
    await state.update_data(days_due=value)
    data = await state.get_data()
    await state.set_state(OnboardingStates.confirm)
    await answer_with_decision_keyboard(
        message,
        _summary(data),
        save_cancel_keyboard(save_label='Uložiť profil'),
    )


@router.message(OnboardingStates.confirm)
async def onboarding_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    if canonical_decision is None:
        answer = await resolve_yes_no(
            context_name='onboarding_confirm',
            user_input_text=(message.text or ''),
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    else:
        answer = canonical_decision if canonical_decision in {'yes', 'no', 'unknown'} else 'unknown'
    if answer == 'unknown':
        await message.answer('Napíšte ano alebo nie.')
        return

    if answer == 'no':
        await state.clear()
        await message.answer('Onboarding bol zrušený. Pre nový pokus spustite /moj_profil.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    mode = str(data.get(_ONBOARDING_MODE_KEY) or 'legacy')
    profile = SupplierProfile(
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
    issue_year = int(data['invoice_number_issue_year'])
    first_invoice_number = str(data['first_invoice_number'])

    if mode in {CREATE_FIRST_WORKSPACE_PROFILE, CREATE_ADDITIONAL_WORKSPACE_PROFILE}:
        context = WorkspaceProfileService(config.db_path).create_profile(
            actor_telegram_id=message.from_user.id,
            profile=profile,
            mode=mode,
            make_active=mode == CREATE_FIRST_WORKSPACE_PROFILE,
        )
        WorkspaceInvoiceService(config.db_path).set_first_invoice_number(
            context,
            issue_year=issue_year,
            first_invoice_number=first_invoice_number,
        )
        if mode == CREATE_ADDITIONAL_WORKSPACE_PROFILE:
            await state.update_data(
                **{_ONBOARDING_WORKSPACE_ID_KEY: context.workspace_id}
            )
            await state.set_state(OnboardingStates.waiting_activation_confirm)
            await message.answer(
                f'Profil {context.workspace_display_name} bol uložený. '
                'Nastaviť ho ako aktívny profil? Odpovedzte ano alebo nie.'
            )
            return
    elif mode == 'update_workspace':
        workspace_id = str(data.get(_ONBOARDING_WORKSPACE_ID_KEY) or '').strip()
        try:
            context = WorkspaceContextService(config.db_path).require_membership(
                message.from_user.id,
                workspace_id,
            )
        except WorkspaceContextError:
            await state.clear()
            await message.answer('Business profil tohto onboardingu už nie je dostupný.')
            return
        SupplierService(config.db_path).update_profile(
            replace(profile, workspace_id=workspace_id)
        )
        WorkspaceInvoiceService(config.db_path).set_first_invoice_number(
            context,
            issue_year=issue_year,
            first_invoice_number=first_invoice_number,
        )
    else:
        SupplierService(config.db_path).create_or_replace(profile)
        InvoiceService(config.db_path).set_first_invoice_number(
            supplier_telegram_id=message.from_user.id,
            issue_year=issue_year,
            first_invoice_number=first_invoice_number,
        )

    await state.clear()
    await message.answer(SUPPLIER_ONBOARDING_SAVED_NEXT_STEP_MESSAGE)

@router.message(OnboardingStates.waiting_activation_confirm)
async def onboarding_activation_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_yes_no(
        context_name='additional_workspace_activation_confirm',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer('Napíšte ano alebo nie.')
        return
    data = await state.get_data()
    workspace_id = str(data.get(_ONBOARDING_WORKSPACE_ID_KEY) or '').strip()
    if message.from_user is None or not workspace_id:
        await state.clear()
        await message.answer('Nový business profil už nie je dostupný.')
        return
    try:
        context = WorkspaceContextService(config.db_path).require_membership(
            message.from_user.id,
            workspace_id,
        )
        if decision == 'yes':
            WorkspaceContextService(config.db_path).set_active_workspace(
                message.from_user.id,
                workspace_id,
            )
    except WorkspaceContextError:
        await state.clear()
        await message.answer('Nový business profil už nie je dostupný.')
        return
    await state.clear()
    if decision == 'yes':
        await message.answer(
            f'Aktívny firemný profil bol zmenený na {context.workspace_display_name}.'
        )
    else:
        await message.answer(
            f'Profil {context.workspace_display_name} bol uložený; aktívny profil sa nezmenil.'
        )
