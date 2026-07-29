from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import re
import secrets

from bot.config import Config
from bot.keyboards.decision import answer_with_decision_keyboard, save_cancel_keyboard
from bot.services.document_intake import extract_message_document_text
from bot.services.llm_contact_parser import extract_contact_draft
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.decision_resolver import resolve_yes_no
from bot.services.semantic_action_resolver import resolve_semantic_action
from bot.services.registry_contact_save import (
    RegistryContactConflict,
    RegistryContactDraft,
    RegistryContactSaveService,
)
from bot.services.slovak_company_registry import (
    RegistryCompanyCandidate,
    RegistryCompanyDetails,
    RegistryLookupError,
    SlovakCompanyRegistry,
)
from bot.services.slovak_tax_registry import (
    SlovakCompanyDetailsAggregator,
    SlovakTaxRegistry,
    TaxDetailsProvider,
    verified_financna_sprava_schema,
)
from bot.services.supplier_service import SupplierService
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_context import (
    WorkspaceContext,
    WorkspaceContextError,
    WorkspaceContextService,
)
from bot.services.validation import (
    normalize_contact_iban,
    validate_contact_address,
    validate_contact_iban,
    validate_dic,
    validate_email,
    validate_ic_dph,
    validate_ico,
)

router = Router(name='contacts')
logger = logging.getLogger(__name__)


CONTACT_INTAKE_TIMEOUT_SECONDS = 5 * 60
CONTACT_TIMEOUT_MESSAGE = (
    'Vytváranie kontaktu bolo ukončené z dôvodu nečinnosti. '
    'Keď budete pripravený, začnite kontakt znova.'
)
CONTACT_RECOVERY_HINT = (
    'Ak chcete vytváranie kontaktu zrušiť, napíšte "zrušiť". '
    'Alebo sa vráťte do hlavného menu: /menu'
)
_CONTACT_EXPIRES_AT_KEY = 'contact_intake_expires_at'

_CONTACT_WORKSPACE_ID_KEY = 'contact_workspace_id'
_REGISTRY_SESSION_KEY = 'contact_registry_session'
_REGISTRY_PICK_PREFIX = 'contact_registry_pick:'
_REGISTRY_ACTION_PREFIX = 'contact_registry_action:'
_REGISTRY_STALE_MESSAGE = 'Toto vyhľadávanie už nie je dostupné. Spustite /contact znova.'


def _resolve_contact_scope(config: Config, telegram_id: int) -> WorkspaceContext | None:
    try:
        return WorkspaceContextService(config.db_path).resolve_for_user(telegram_id)
    except WorkspaceContextError as workspace_error:
        try:
            legacy_supplier = SupplierService(config.db_path).get_by_telegram_id(telegram_id)
        except RuntimeError:
            raise workspace_error
        if legacy_supplier is not None and legacy_supplier.workspace_id is None:
            return None
        raise workspace_error


async def _bind_contact_scope(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
) -> tuple[bool, WorkspaceContext | None]:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return False, None
    try:
        context = _resolve_contact_scope(config, message.from_user.id)
    except WorkspaceContextError:
        await message.answer('Aktívny business profil nie je dostupný alebo nie je vybraný.')
        return False, None
    if context is None:
        supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    else:
        supplier = SupplierService(config.db_path).get_by_workspace_id(context.workspace_id)
    if supplier is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /moj_profil.')
        return False, None
    await state.update_data(
        **{_CONTACT_WORKSPACE_ID_KEY: context.workspace_id if context is not None else ''}
    )
    return True, context


async def _contact_scope_from_state(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
) -> WorkspaceContext | None:
    if message.from_user is None:
        raise WorkspaceContextError('contact_actor_required')
    data = await state.get_data()
    workspace_id = str(data.get(_CONTACT_WORKSPACE_ID_KEY) or '').strip()
    if not workspace_id:
        return None
    return WorkspaceContextService(config.db_path).require_membership(
        message.from_user.id,
        workspace_id,
    )


async def _get_contact_by_name_for_scope(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    name: str,
) -> ContactProfile | None:
    context = await _contact_scope_from_state(
        message=message,
        state=state,
        config=config,
    )
    if context is None:
        if message.from_user is None:
            return None
        return ContactService(config.db_path).get_by_name(message.from_user.id, name)
    return WorkspaceContactService(config.db_path).get_by_name(context, name)

async def _save_contact_for_scope(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    profile: ContactProfile,
) -> None:
    context = await _contact_scope_from_state(
        message=message,
        state=state,
        config=config,
    )
    if context is None:
        ContactService(config.db_path).create_or_replace(profile)
        return
    WorkspaceContactService(config.db_path).create_or_replace(
        context,
        replace(profile, workspace_id=context.workspace_id),
    )


def _with_contact_recovery_hint(message: str) -> str:
    return f'{message}\n\n{CONTACT_RECOVERY_HINT}'


def _contact_session_metadata(now: datetime | None = None) -> dict[str, str]:
    expires_at = _utc_now(now) + timedelta(seconds=CONTACT_INTAKE_TIMEOUT_SECONDS)
    return {_CONTACT_EXPIRES_AT_KEY: expires_at.isoformat()}


async def _ensure_contact_session_active(
    *,
    message: Message,
    state: FSMContext,
    now: datetime | None = None,
) -> bool:
    data = await state.get_data()
    expires_at = _parse_contact_timestamp(data.get(_CONTACT_EXPIRES_AT_KEY))
    current_time = _utc_now(now)
    if expires_at is not None and current_time >= expires_at:
        await state.clear()
        await message.answer(CONTACT_TIMEOUT_MESSAGE)
        return False

    updates: dict[str, object] = _contact_session_metadata(now=current_time)
    raw_registry_session = data.get(_REGISTRY_SESSION_KEY)
    if isinstance(raw_registry_session, dict) and raw_registry_session:
        registry_session = dict(raw_registry_session)
        registry_session['expires_at'] = updates[_CONTACT_EXPIRES_AT_KEY]
        updates[_REGISTRY_SESSION_KEY] = registry_session
    await state.update_data(**updates)
    return True


def _utc_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _parse_contact_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return _utc_now(parsed)

class ContactStates(StatesGroup):
    name_hint = State()
    source_after_name = State()
    ico = State()
    dic = State()
    ic_dph = State()
    address = State()
    email = State()
    iban = State()
    contact_person = State()
    registry_candidates = State()
    registry_detail_preview = State()
    registry_fallback = State()
    registry_required_dic = State()
    registry_optional_email = State()
    registry_optional_iban = State()
    registry_optional_contact_person = State()
    registry_final_confirm = State()
    confirm = State()
    intake_missing = State()
    intake_confirm = State()


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
        f'Email: {data["email"] or "-"}\n'
        f'IBAN: {data.get("iban") or "-"}\n'
        f'Kontaktná osoba: {data["contact_person"] or "-"}'
        f'{duplicate_note}\n\n'
        'Napíšte ano pre uloženie alebo nie pre zrušenie.'
    )


def _contact_draft_summary(data: dict[str, str]) -> str:
    return (
        'Návrh kontaktu\n\n'
        f'Názov: {data.get("name") or "-"}\n'
        f'ICO: {data.get("ico") or "-"}\n'
        f'DIC: {data.get("dic") or "-"}\n'
        f'IC DPH: {data.get("ic_dph") or "-"}\n'
        f'Adresa: {data.get("address") or "-"}\n'
        f'Email: {data.get("email") or "-"}\n'
        f'IBAN: {data.get("iban") or "-"}\n'
        f'Kontaktná osoba: {data.get("contact_person") or "-"}\n\n'
        'Napíšte ano pre uloženie alebo nie pre zrušenie.'
    )


def _missing_prompt(field: str) -> str:
    if field == 'address':
        return 'Nepodarilo sa jednoznačne určiť adresu vrátane čísla domu. Príklad: Hlavná 1, Košice.'
    if field == 'name':
        return 'Nepodarilo sa jednoznačne určiť názov spoločnosti. Spresnite ho, prosím.'
    if field == 'ico':
        return 'Nepodarilo sa nájsť IČO. Doplňte ho, prosím.'
    if field == 'dic':
        return 'Nepodarilo sa nájsť DIČ. Doplňte ho, prosím.'
    if field == 'iban':
        return 'IBAN v dokumente nie je platný. Zadajte platný IBAN alebo pošlite "-".'
    return 'Doplňte chýbajúce údaje, prosím.'


def _missing_required_fields(data: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for field in ('name', 'ico', 'dic'):
        if not str(data.get(field, '')).strip():
            missing.append(field)
    if not validate_contact_address(str(data.get('address', ''))):
        missing.append('address')
    iban = str(data.get('iban', '')).strip()
    if iban and not validate_contact_iban(iban):
        missing.append('iban')
    return missing


def _extract_company_hint(text: str) -> str | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    patterns = [
        r'(?:firmu|firma|spoločnosť|company)\s+([A-Za-zÀ-ž0-9 .,&\-]{2,80})',
        r'(?:kontakt(?:ov)?|контакт(?:а|у)?)\s+([A-Za-zÀ-ž0-9 .,&\-]{2,80})',
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(' ,.;:')
    return None


def _registry_enabled(config: Config, context: WorkspaceContext | None) -> bool:
    if not config.contact_registry_lookup_enabled or context is None:
        return False
    pilots = config.contact_registry_pilot_workspace_ids
    return not pilots or context.workspace_id in pilots


def _registry_client(config: Config) -> SlovakCompanyRegistry:
    return SlovakCompanyRegistry(
        timeout_seconds=config.contact_registry_timeout_seconds,
        max_results=config.contact_registry_max_results,
    )


def _tax_registry_client(config: Config) -> TaxDetailsProvider | None:
    schema = verified_financna_sprava_schema()
    if (
        not config.contact_tax_lookup_enabled
        or not config.financna_sprava_api_key
        or schema is None
    ):
        return None
    return SlovakTaxRegistry(
        enabled=True,
        api_key=config.financna_sprava_api_key,
        schema=schema,
        timeout_seconds=config.financna_sprava_timeout_seconds,
    )


def _registry_details_aggregator(config: Config) -> SlovakCompanyDetailsAggregator:
    return SlovakCompanyDetailsAggregator(
        registry=_registry_client(config),
        tax_registry=_tax_registry_client(config),
    )


def _candidate_data(candidate: RegistryCompanyCandidate) -> dict[str, object]:
    return {
        'subject_id': candidate.subject_id,
        'name': candidate.name,
        'ico': candidate.ico,
        'city': candidate.city,
        'short_address': candidate.short_address,
        'is_active': candidate.is_active,
        'provider': candidate.provider,
        'match_kind': candidate.match_kind,
    }


def _registry_candidate_keyboard(nonce: str, candidates: list[RegistryCompanyCandidate]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f'{candidate.name[:38]} · {candidate.ico}',
                callback_data=f'{_REGISTRY_PICK_PREFIX}{nonce}:{index}',
            )
        ]
        for index, candidate in enumerate(candidates)
    ]
    rows.append(
        [
            InlineKeyboardButton(
                text='Zadať ručne',
                callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:manual',
            ),
            InlineKeyboardButton(
                text='Zrušiť',
                callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:cancel',
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _registry_preview_keyboard(nonce: str, *, can_save: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text='Doplniť údaje',
                callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:supplement',
            )
        ]
    ]
    if can_save:
        rows.append(
            [
                InlineKeyboardButton(
                    text='Uložiť',
                    callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:save',
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text='Zadať ručne',
                callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:manual',
            ),
            InlineKeyboardButton(
                text='Zrušiť',
                callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:cancel',
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _registry_fallback_keyboard(nonce: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Skúsiť znova',
                    callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:retry',
                ),
                InlineKeyboardButton(
                    text='Zadať ručne',
                    callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:manual',
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Zrušiť',
                    callback_data=f'{_REGISTRY_ACTION_PREFIX}{nonce}:cancel',
                )
            ],
        ]
    )


def _registry_details_data(details: RegistryCompanyDetails) -> dict[str, object]:
    return {
        'subject_id': details.subject_id,
        'name': details.name,
        'ico': details.ico,
        'dic': details.dic or '',
        'ic_dph': details.ic_dph or '',
        'address': details.address or '',
        'city': details.city or '',
        'is_active': details.is_active,
        'provider_sources': list(details.provider_sources),
        'email': '',
        'iban': '',
        'contact_person': '',
        'email_supplied': False,
        'iban_supplied': False,
        'contact_person_supplied': False,
    }


def _registry_tax_preview_note(draft: dict[str, object]) -> str:
    sources = {str(value) for value in draft.get('provider_sources') or []}
    tax_enriched = 'financna_sprava' in sources
    dic_valid = validate_dic(str(draft.get('dic') or ''))
    ic_dph_valid = validate_ic_dph(str(draft.get('ic_dph') or ''))

    if tax_enriched and dic_valid and ic_dph_valid:
        return 'DIČ a IČ DPH boli získané a overené z oficiálnych zdrojov. Žiadna hodnota sa neodvodzuje ani nevytvára.'
    if tax_enriched and dic_valid:
        return 'DIČ bolo získané a overené z oficiálneho zdroja. IČ DPH sa pre vybrané IČO v oficiálnom zozname nenašlo; z DIČ sa nevytvára ani neodvodzuje.'
    if tax_enriched and ic_dph_valid:
        return 'IČ DPH bolo získané a overené z oficiálneho zdroja. DIČ sa nepodarilo získať a treba ho doplniť textom.'
    if dic_valid and ic_dph_valid:
        return 'DIČ a IČ DPH sú vyplnené a formátovo overené. IČ DPH sa z DIČ neodvodzuje.'
    if dic_valid:
        return 'DIČ je vyplnené a formátovo overené. IČ DPH nie je vyplnené a z DIČ sa nevytvára ani neodvodzuje.'
    if ic_dph_valid:
        return 'IČ DPH je vyplnené a formátovo overené. Chýbajúce DIČ treba doplniť textom.'
    return 'DIČ sa nepodarilo získať a treba ho doplniť textom. IČ DPH sa z DIČ nevytvára ani neodvodzuje.'


def _registry_preview_text(draft: dict[str, object]) -> str:
    status = 'aktívna' if draft.get('is_active') is True else ('neaktívna' if draft.get('is_active') is False else '-')
    sources = ' + '.join(str(value) for value in draft.get('provider_sources') or []) or 'slovak_rpo'
    return (
        'Údaje z oficiálneho registra\n\n'
        f'Názov: {draft.get("name") or "-"}\n'
        f'IČO: {draft.get("ico") or "-"}\n'
        f'DIČ: {draft.get("dic") or "-"}\n'
        f'IČ DPH: {draft.get("ic_dph") or "-"}\n'
        f'Adresa: {draft.get("address") or "-"}\n'
        f'Email: {draft.get("email") or "-"}\n'
        f'IBAN: {draft.get("iban") or "-"}\n'
        f'Kontaktná osoba: {draft.get("contact_person") or "-"}\n'
        f'Stav: {status}\n'
        f'Zdroj: {sources}\n\n'
        f'{_registry_tax_preview_note(draft)}'
    )


def _registry_required_complete(draft: dict[str, object]) -> bool:
    return (
        bool(str(draft.get('name') or '').strip())
        and validate_ico(str(draft.get('ico') or ''))
        and validate_dic(str(draft.get('dic') or ''))
        and validate_contact_address(str(draft.get('address') or ''))
    )


async def _show_registry_fallback(*, message, state: FSMContext, reason: str) -> None:
    data = await state.get_data()
    session = dict(data.get(_REGISTRY_SESSION_KEY) or {})
    nonce = str(session.get('nonce') or secrets.token_urlsafe(6))
    session['nonce'] = nonce
    await state.update_data(**{_REGISTRY_SESSION_KEY: session})
    await state.set_state(ContactStates.registry_fallback)
    await message.answer(
        f'{reason}\nMôžete skúsiť vyhľadávanie znova alebo pokračovať ručne/PDF.',
        reply_markup=_registry_fallback_keyboard(nonce),
    )


async def _load_registry_details(
    *,
    message,
    state: FSMContext,
    config: Config,
    subject_id: str,
) -> None:
    try:
        aggregated = await _registry_details_aggregator(config).get_details(subject_id)
        details = aggregated.details
    except RegistryLookupError:
        await _show_registry_fallback(
            message=message,
            state=state,
            reason='Detail firmy sa z registra nepodarilo načítať.',
        )
        return
    draft = _registry_details_data(details)
    if not draft['name'] or not draft['ico'] or not validate_contact_address(str(draft['address'])):
        await _show_registry_fallback(
            message=message,
            state=state,
            reason='Register nevrátil použiteľné povinné údaje firmy.',
        )
        return
    data = await state.get_data()
    session = dict(data.get(_REGISTRY_SESSION_KEY) or {})
    session['selected_subject_id'] = subject_id
    await state.update_data(
        **{
            _REGISTRY_SESSION_KEY: session,
            'contact_registry_draft': draft,
        }
    )
    await state.set_state(ContactStates.registry_detail_preview)
    await message.answer(
        _registry_preview_text(draft),
        reply_markup=_registry_preview_keyboard(
            str(session['nonce']),
            can_save=_registry_required_complete(draft),
        ),
    )


async def _start_registry_search(
    *,
    message,
    state: FSMContext,
    config: Config,
    query: str,
    context: WorkspaceContext,
    actor_telegram_id: int | None = None,
) -> None:
    actor_id = actor_telegram_id or (message.from_user.id if message.from_user else 0)
    session = {
        'nonce': secrets.token_urlsafe(6),
        'actor_telegram_id': actor_id,
        'workspace_id': context.workspace_id,
        'query': query,
        'expires_at': (_utc_now() + timedelta(seconds=CONTACT_INTAKE_TIMEOUT_SECONDS)).isoformat(),
        'candidates': [],
    }
    await state.update_data(**{_REGISTRY_SESSION_KEY: session})
    try:
        candidates = await _registry_client(config).search(query)
    except RegistryLookupError:
        await _show_registry_fallback(
            message=message,
            state=state,
            reason='Oficiálny register je momentálne nedostupný.',
        )
        return
    if not candidates:
        await _show_registry_fallback(
            message=message,
            state=state,
            reason='V oficiálnom registri sa nenašla zodpovedajúca firma.',
        )
        return
    session['candidates'] = [_candidate_data(candidate) for candidate in candidates]
    await state.update_data(**{_REGISTRY_SESSION_KEY: session})
    if len(candidates) == 1 and candidates[0].match_kind in {
        'exact_ico', 'exact_name',
    }:
        await _load_registry_details(
            message=message,
            state=state,
            config=config,
            subject_id=candidates[0].subject_id,
        )
        return
    await state.set_state(ContactStates.registry_candidates)
    lines = ['Vyberte správnu firmu:']
    for index, candidate in enumerate(candidates, start=1):
        locality = candidate.city or candidate.short_address or '-'
        lines.append(f'\n{index}. {candidate.name}\nIČO: {candidate.ico}\n{locality}')
    await message.answer(
        '\n'.join(lines),
        reply_markup=_registry_candidate_keyboard(str(session['nonce']), candidates),
    )


def _registry_contact_draft(data: dict[str, object]) -> RegistryContactDraft:
    draft = dict(data.get('contact_registry_draft') or {})
    return RegistryContactDraft(
        name=str(draft.get('name') or '').strip(),
        ico=str(draft.get('ico') or '').strip(),
        dic=str(draft.get('dic') or '').strip(),
        ic_dph=str(draft.get('ic_dph') or '').strip() or None,
        address=str(draft.get('address') or '').strip(),
        email=str(draft.get('email') or '').strip() or None,
        iban=str(draft.get('iban') or '').strip() or None,
        contact_person=str(draft.get('contact_person') or '').strip() or None,
        provider_sources=tuple(str(value) for value in draft.get('provider_sources') or ('slovak_rpo',)),
        email_supplied=bool(draft.get('email_supplied')),
        iban_supplied=bool(draft.get('iban_supplied')),
        contact_person_supplied=bool(draft.get('contact_person_supplied')),
    )


async def _registry_context_for_actor(
    *,
    actor_telegram_id: int,
    state: FSMContext,
    config: Config,
) -> WorkspaceContext:
    data = await state.get_data()
    session = dict(data.get(_REGISTRY_SESSION_KEY) or {})
    expected_workspace = str(session.get('workspace_id') or '')
    context = WorkspaceContextService(config.db_path).resolve_for_user(actor_telegram_id)
    if context.workspace_id != expected_workspace:
        raise WorkspaceContextError('registry_active_workspace_changed')
    return context


async def _enter_registry_final_confirmation(
    *,
    message,
    state: FSMContext,
    config: Config,
    actor_telegram_id: int,
) -> None:
    try:
        context = await _registry_context_for_actor(
            actor_telegram_id=actor_telegram_id,
            state=state,
            config=config,
        )
        draft = _registry_contact_draft(await state.get_data())
        inspection = RegistryContactSaveService(config.db_path).inspect(context, draft)
    except (WorkspaceContextError, ValueError):
        await state.clear()
        await message.answer('Kontakt sa nedá uložiť, pretože profil alebo povinné údaje už nie sú platné.')
        return
    if inspection.mode in {'name_conflict', 'split_conflict', 'ico_conflict'}:
        await state.set_state(ContactStates.registry_detail_preview)
        await message.answer(
            'Našiel sa konflikt medzi názvom a IČO existujúcich kontaktov. Nič som nezmenil. '
            'Pokračujte ručne alebo kontakt najprv skontrolujte.'
        )
        return
    data = await state.get_data()
    raw_draft = dict(data.get('contact_registry_draft') or {})
    mode_note = (
        'Existujúci kontakt s rovnakým IČO sa aktualizuje; jeho ID a prepojené faktúry zostanú zachované.'
        if inspection.mode == 'update'
        else 'Vytvorí sa nový kontakt v aktívnom business profile.'
    )
    summary = (
        f'{_registry_preview_text(raw_draft)}\n'
        f'Email: {raw_draft.get("email") or (inspection.existing.email if inspection.existing else "-")}\n'
        f'IBAN: {raw_draft.get("iban") or (inspection.existing.iban if inspection.existing else "-")}\n'
        f'Kontaktná osoba: {raw_draft.get("contact_person") or (inspection.existing.contact_person if inspection.existing else "-")}\n\n'
        f'{mode_note}\n\nPotvrďte uloženie.'
    )
    await state.update_data(contact_registry_save_mode=inspection.mode)
    await state.set_state(ContactStates.registry_final_confirm)
    await answer_with_decision_keyboard(message, summary, save_cancel_keyboard())


async def _registry_manual_fallback(*, message, state: FSMContext) -> None:
    data = await state.get_data()
    session = dict(data.get(_REGISTRY_SESSION_KEY) or {})
    query = str(session.get('query') or '').strip()
    if validate_ico(query):
        await state.set_state(ContactStates.name_hint)
        await message.answer(_with_contact_recovery_hint('Zadajte názov firmy pre ručné pokračovanie.'))
        return
    await state.update_data(contact_company_hint=query, name=query, existing_match='0')
    await state.set_state(ContactStates.source_after_name)
    await message.answer('Pošlite zmluvu/PDF alebo zadajte IČO.')

async def start_add_contact_intake(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    await state.clear()
    scope_ready, _context = await _bind_contact_scope(
        message=message,
        state=state,
        config=config,
    )
    if not scope_ready:
        return
    await state.update_data(**_contact_session_metadata())
    await state.set_state(ContactStates.name_hint)
    await message.answer(
        _with_contact_recovery_hint('Zadajte názov firmy alebo IČO.')
    )


async def _start_add_contact_from_source(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    source_text: str,
    document_text: str | None = None,
    contract_path: str | None = None,
    company_hint: str | None = None,
) -> None:
    scope_data = await state.get_data()
    if _CONTACT_WORKSPACE_ID_KEY not in scope_data:
        scope_ready, _context = await _bind_contact_scope(
            message=message,
            state=state,
            config=config,
        )
        if not scope_ready:
            return
    extraction_source = '\n'.join(part for part in [source_text, document_text or ''] if part.strip())
    resolved_company_hint = company_hint or _extract_company_hint(source_text)
    parsed = await extract_contact_draft(
        source_text=extraction_source,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        company_hint=resolved_company_hint,
    )
    parsed_iban = str(parsed.get('iban') or '').strip()
    if parsed_iban and validate_contact_iban(parsed_iban):
        parsed_iban = normalize_contact_iban(parsed_iban)
    await state.update_data(**_contact_session_metadata())
    if parsed.get('role_ambiguity') == '1':
        partial_draft = {
            'name': resolved_company_hint or parsed.get('company_name') or '',
            'ico': parsed.get('ico') or '',
            'dic': parsed.get('dic') or '',
            'ic_dph': parsed.get('ic_dph') or '',
            'address': parsed.get('address') or '',
            'email': parsed.get('email') or '',
            'iban': parsed_iban,
            'contact_person': parsed.get('contact_person') or '',
            'contract_path': contract_path or '',
        }
        missing = _missing_required_fields(partial_draft)
        if 'name' not in missing:
            missing.insert(0, 'name')
        await message.answer(
            'V zmluve je nejasné, ktorú stranu chcete uložiť ako kontakt. '
            'Uveďte, prosím, presný názov firmy odberateľa.'
        )
        await state.set_state(ContactStates.intake_missing)
        await state.update_data(
            contact_intake_draft=partial_draft,
            contact_missing_fields=missing,
            contract_path=contract_path or '',
        )
        return

    draft = {
        'name': parsed.get('company_name') or '',
        'ico': parsed.get('ico') or '',
        'dic': parsed.get('dic') or '',
        'ic_dph': parsed.get('ic_dph') or '',
        'address': parsed.get('address') or '',
        'email': parsed.get('email') or '',
        'iban': parsed_iban,
        'contact_person': parsed.get('contact_person') or '',
        'contract_path': contract_path or '',
    }
    missing = _missing_required_fields(draft)
    await state.update_data(contact_intake_draft=draft, contact_missing_fields=missing)
    if missing:
        await state.set_state(ContactStates.intake_missing)
        await message.answer(_missing_prompt(missing[0]))
        return

    await state.set_state(ContactStates.intake_confirm)
    await answer_with_decision_keyboard(message, _contact_draft_summary(draft), save_cancel_keyboard())


async def process_contact_missing_fields(
    *,
    message: Message,
    state: FSMContext,
    user_text: str,
) -> None:
    data = await state.get_data()
    missing = list(data.get('contact_missing_fields') or [])
    draft = dict(data.get('contact_intake_draft') or {})
    if not missing:
        await state.set_state(ContactStates.intake_confirm)
        await answer_with_decision_keyboard(message, _contact_draft_summary(draft), save_cancel_keyboard())
        return

    current = missing[0]
    value = user_text.strip()
    if not value:
        await message.answer(_with_contact_recovery_hint(_missing_prompt(current)))
        return

    if current == 'email' and not validate_email(value):
        if value == '-':
            draft[current] = ''
            missing = missing[1:]
            await state.update_data(contact_intake_draft=draft, contact_missing_fields=missing)
            if missing:
                await message.answer(_missing_prompt(missing[0]))
                return
            await state.set_state(ContactStates.intake_confirm)
            await answer_with_decision_keyboard(message, _contact_draft_summary(draft), save_cancel_keyboard())
            return
        await message.answer(_with_contact_recovery_hint('Neplatný email. Skúste znova:'))
        return
    if current == 'iban':
        if value == '-':
            draft[current] = ''
        elif not validate_contact_iban(value):
            await message.answer(_with_contact_recovery_hint('Neplatný IBAN. Skúste znova alebo pošlite "-".'))
            return
        else:
            draft[current] = normalize_contact_iban(value)
        missing = missing[1:]
        await state.update_data(contact_intake_draft=draft, contact_missing_fields=missing)
        if missing:
            await message.answer(_missing_prompt(missing[0]))
            return
        await state.set_state(ContactStates.intake_confirm)
        await answer_with_decision_keyboard(message, _contact_draft_summary(draft), save_cancel_keyboard())
        return
    if current == 'address' and not validate_contact_address(value):
        await message.answer(
            _with_contact_recovery_hint('Adresa musí obsahovať aj číslo domu. Príklad: Hlavná 1, Košice.')
        )
        return
    if current == 'ico' and not validate_ico(value):
        await message.answer(_with_contact_recovery_hint('Neplatné ICO. Formát: 8 číslic. Skúste znova:'))
        return
    if current == 'dic' and not validate_dic(value):
        await message.answer(_with_contact_recovery_hint('Neplatné DIC. Formát: 10 číslic. Skúste znova:'))
        return

    draft[current] = value
    missing = missing[1:]
    await state.update_data(contact_intake_draft=draft, contact_missing_fields=missing)
    if missing:
        await message.answer(_missing_prompt(missing[0]))
        return

    await state.set_state(ContactStates.intake_confirm)
    await answer_with_decision_keyboard(message, _contact_draft_summary(draft), save_cancel_keyboard())


async def process_contact_intake_confirm(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    answer_text: str,
    canonical_decision: str | None = None,
) -> None:
    if canonical_decision is None:
        answer = await resolve_yes_no(
            context_name='contact_intake_confirm',
            user_input_text=answer_text,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    else:
        answer = canonical_decision if canonical_decision in {'yes', 'no', 'unknown'} else 'unknown'
    if answer == 'unknown':
        await message.answer(_with_contact_recovery_hint('Napíšte ano alebo nie.'))
        return
    if answer == 'no':
        await state.clear()
        await message.answer('Vytvorenie kontaktu bolo zrušené.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    draft = dict(data.get('contact_intake_draft') or {})
    try:
        await _save_contact_for_scope(
            message=message,
            state=state,
            config=config,
            profile=ContactProfile(
            supplier_telegram_id=message.from_user.id,
            name=draft['name'],
            ico=draft['ico'],
            dic=draft['dic'],
            ic_dph=draft.get('ic_dph') or None,
            address=draft['address'],
            email=draft['email'],
            iban=draft.get('iban') or None,
            contact_person=draft.get('contact_person') or None,
            source_type='contract_intake',
            source_note='semantic_intake',
            contract_path=draft.get('contract_path') or None,
            ),
        )
    except WorkspaceContextError:
        await state.clear()
        await message.answer('Business profil kontaktu už nie je dostupný.')
        return
    await state.clear()
    await message.answer('Kontakt bol uložený.')


@router.message(Command('contact', 'contact_add', 'add_kontakt'))
async def cmd_contact(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    existing_state = await state.get_state()
    if existing_state is not None:
        await message.answer('Flow kontaktu bol reštartovaný. Predchádzajúci draft bol zahodený.')

    await start_add_contact_intake(message=message, state=state, config=config)


async def _process_source_after_name_step(message: Message, state: FSMContext, config: Config, bot=None) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    state_data = await state.get_data()
    company_hint = str(state_data.get('contact_company_hint') or '').strip()

    if message.document is not None:
        if bot is None:
            await message.answer('Nepodarilo sa spracovať dokument. Skúste ho poslať znova.')
            return
        result = await extract_message_document_text(message, bot, config.storage_dir)
        if result.status == 'unsupported':
            await message.answer('Tento typ prílohy zatiaľ nepodporujem. Pošlite, prosím, PDF dokument.')
            return
        if result.status == 'scan_pdf_needs_ocr':
            await message.answer(
                'Dokument je sken bez textovej vrstvy. OCR režim zatiaľ nie je dostupný, '
                'pošlite textové PDF alebo doplňte údaje ručne.'
            )
            return

        caption = (message.caption or '').strip()
        await _start_add_contact_from_source(
            message=message,
            state=state,
            config=config,
            source_text=company_hint or caption,
            document_text=result.extracted_text,
            contract_path=str(result.saved_path) if result.saved_path else None,
            company_hint=company_hint or _extract_company_hint(caption),
        )
        return

    value = (message.text or '').strip()
    if not value:
        await message.answer(_with_contact_recovery_hint('Pošlite zmluvu/PDF alebo zadajte IČO.'))
        return

    if not validate_ico(value):
        await message.answer(_with_contact_recovery_hint('Neplatné ICO. Formát: 8 číslic. Skúste znova:'))
        return

    await state.update_data(ico=value)
    await state.set_state(ContactStates.dic)
    await message.answer('3/8 Zadajte DIC (10 číslic):')


@router.message(ContactStates.name_hint)
async def contact_name_hint(message: Message, state: FSMContext, config: Config) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    if message.document is not None:
        await message.answer(_with_contact_recovery_hint('V tomto kroku najprv zadajte názov firmy textom.'))
        return

    value = (message.text or '').strip()
    if not value:
        await message.answer(_with_contact_recovery_hint('Zadajte názov firmy.'))
        return


    try:
        context = await _contact_scope_from_state(message=message, state=state, config=config)
    except WorkspaceContextError:
        await state.clear()
        await message.answer('Business profil kontaktu už nie je dostupný.')
        return
    if _registry_enabled(config, context):
        await _start_registry_search(
            message=message,
            state=state,
            config=config,
            query=value,
            context=context,
        )
        return
    if validate_ico(value):
        await message.answer(
            _with_contact_recovery_hint(
                'Vyhľadávanie v registri nie je pre tento profil zapnuté. Zadajte názov firmy.'
            )
        )
        return

    try:
        existing = await _get_contact_by_name_for_scope(
            message=message,
            state=state,
            config=config,
            name=value,
        )
    except WorkspaceContextError:
        await state.clear()
        await message.answer('Business profil kontaktu už nie je dostupný.')
        return
    if existing is not None:
        await message.answer(
            'Kontakt s týmto presným názvom už existuje. '
            'Pokračujte a po potvrdení sa prepíše.'
        )

    await state.update_data(
        contact_company_hint=value,
        name=value,
        existing_match='1' if existing is not None else '0',
    )
    await state.set_state(ContactStates.source_after_name)
    await message.answer('Pošlite zmluvu/PDF alebo zadajte IČO.')


@router.message(ContactStates.source_after_name)
async def contact_source_after_name(message: Message, state: FSMContext, config: Config, bot) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    await _process_source_after_name_step(message, state, config, bot)


@router.message(ContactStates.ico)
async def contact_ico(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    value = (message.text or '').strip()
    if not validate_ico(value):
        await message.answer(_with_contact_recovery_hint('Neplatné ICO. Formát: 8 číslic. Skúste znova:'))
        return
    await state.update_data(ico=value)
    await state.set_state(ContactStates.dic)
    await message.answer('3/8 Zadajte DIC (10 číslic):')


@router.message(ContactStates.dic)
async def contact_dic(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer(_with_contact_recovery_hint('Neplatné DIC. Formát: 10 číslic. Skúste znova:'))
        return
    await state.update_data(dic=value)
    await state.set_state(ContactStates.ic_dph)
    await message.answer('4/8 Zadajte IC DPH (voliteľné, pošlite "-"):')


@router.message(ContactStates.ic_dph)
async def contact_ic_dph(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    value = (message.text or '').strip()
    if value == '-':
        await state.update_data(ic_dph='')
    else:
        if not validate_ic_dph(value):
            await message.answer(
                _with_contact_recovery_hint('Neplatné IC DPH. Príklad: SK1234567890. Skúste znova:')
            )
            return
        await state.update_data(ic_dph=value.upper().replace(' ', ''))

    await state.set_state(ContactStates.address)
    await message.answer('5/8 Zadajte adresu:')


@router.message(ContactStates.address)
async def contact_address(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    value = (message.text or '').strip()
    if not validate_contact_address(value):
        await message.answer(
            _with_contact_recovery_hint('Adresa musí obsahovať aj číslo domu. Príklad: Hlavná 1, Košice.')
        )
        return
    await state.update_data(address=value)
    await state.set_state(ContactStates.email)
    await message.answer('6/8 Zadajte email (voliteľné, pošlite "-", ak ho nechcete uviesť):')


@router.message(ContactStates.email)
async def contact_email(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    value = (message.text or '').strip()
    if value == '-':
        await state.update_data(email='')
        await state.set_state(ContactStates.iban)
        await message.answer('7/8 Zadajte IBAN (voliteľné, pošlite "-"):')
        return
    if not validate_email(value):
        await message.answer(_with_contact_recovery_hint('Neplatný email. Skúste znova:'))
        return
    await state.update_data(email=value)
    await state.set_state(ContactStates.iban)
    await message.answer('7/8 Zadajte IBAN (voliteľné, pošlite "-"):')


@router.message(ContactStates.iban)
async def contact_iban(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    value = (message.text or '').strip()
    if value == '-':
        await state.update_data(iban='')
    elif not validate_contact_iban(value):
        await message.answer(_with_contact_recovery_hint('Neplatný IBAN. Skúste znova alebo pošlite "-".'))
        return
    else:
        await state.update_data(iban=normalize_contact_iban(value))

    await state.set_state(ContactStates.contact_person)
    await message.answer('8/8 Zadajte kontaktnú osobu (voliteľné, pošlite "-"):')


@router.message(ContactStates.contact_person)
async def contact_person(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    value = (message.text or '').strip()
    await state.update_data(contact_person='' if value == '-' else value)

    data = await state.get_data()
    await state.set_state(ContactStates.confirm)
    await answer_with_decision_keyboard(message, _summary(data), save_cancel_keyboard())


@router.message(ContactStates.confirm)
async def contact_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    if canonical_decision is None:
        answer = await resolve_yes_no(
            context_name='contact_confirm',
            user_input_text=(message.text or ''),
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    else:
        answer = canonical_decision if canonical_decision in {'yes', 'no', 'unknown'} else 'unknown'
    if answer == 'unknown':
        await message.answer(_with_contact_recovery_hint('Napíšte ano alebo nie.'))
        return

    if answer == 'no':
        await state.clear()
        await message.answer('Vytvorenie kontaktu bolo zrušené. Pre nový pokus spustite /contact.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    try:
        await _save_contact_for_scope(
            message=message,
            state=state,
            config=config,
            profile=ContactProfile(
            supplier_telegram_id=message.from_user.id,
            name=data['name'],
            ico=data['ico'],
            dic=data['dic'],
            ic_dph=data['ic_dph'] or None,
            address=data['address'],
            email=data['email'],
            iban=data.get('iban') or None,
            contact_person=data['contact_person'] or None,
            source_type='manual',
            source_note=None,
            contract_path=None,
            ),
        )
    except WorkspaceContextError:
        await state.clear()
        await message.answer('Business profil kontaktu už nie je dostupný.')
        return

    await state.clear()
    await message.answer('Kontakt bol uložený.')


def _registry_session_is_expired(session: dict[str, object]) -> bool:
    expires_at = _parse_contact_timestamp(session.get('expires_at'))
    return expires_at is None or _utc_now() >= expires_at


async def _validated_registry_callback(
    *,
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
    allowed_states: set[str],
    nonce: str,
) -> tuple[dict[str, object], WorkspaceContext] | None:
    current_state = await state.get_state()
    if current_state not in allowed_states:
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return None
    data = await state.get_data()
    session = dict(data.get(_REGISTRY_SESSION_KEY) or {})
    if (
        str(session.get('nonce') or '') != nonce
        or int(session.get('actor_telegram_id') or 0) != callback.from_user.id
        or _registry_session_is_expired(session)
    ):
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return None
    try:
        context = WorkspaceContextService(config.db_path).resolve_for_user_readonly(callback.from_user.id)
    except WorkspaceContextError:
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return None
    if context.workspace_id != str(session.get('workspace_id') or '') or not _registry_enabled(config, context):
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return None
    return session, context


async def _refresh_registry_activity(
    *,
    state: FSMContext,
    session: dict[str, object],
) -> dict[str, object]:
    refreshed_session = dict(session)
    refreshed_metadata = _contact_session_metadata()
    refreshed_session['expires_at'] = refreshed_metadata[_CONTACT_EXPIRES_AT_KEY]
    await state.update_data(
        **{
            **refreshed_metadata,
            _REGISTRY_SESSION_KEY: refreshed_session,
        }
    )
    return refreshed_session


async def _clear_registry_keyboard(callback: CallbackQuery) -> None:
    if callback.message is None or not hasattr(callback.message, 'edit_reply_markup'):
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception('Failed to clear contact registry inline keyboard')


@router.callback_query(F.data.startswith(_REGISTRY_PICK_PREFIX))
async def contact_registry_pick_callback(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    payload = (callback.data or '')[len(_REGISTRY_PICK_PREFIX):]
    parts = payload.split(':', 1)
    if len(parts) != 2 or not parts[1].isdigit():
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return
    nonce, raw_index = parts
    validated = await _validated_registry_callback(
        callback=callback,
        state=state,
        config=config,
        allowed_states={ContactStates.registry_candidates.state},
        nonce=nonce,
    )
    if validated is None:
        return
    session, _context = validated
    candidates = list(session.get('candidates') or [])
    index = int(raw_index)
    if index < 0 or index >= len(candidates) or not isinstance(candidates[index], dict):
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return
    subject_id = str(candidates[index].get('subject_id') or '')
    if not subject_id.isdigit() or callback.message is None:
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return
    session = await _refresh_registry_activity(state=state, session=session)
    await _clear_registry_keyboard(callback)
    await _load_registry_details(
        message=callback.message,
        state=state,
        config=config,
        subject_id=subject_id,
    )
    await callback.answer()


@router.callback_query(F.data.startswith(_REGISTRY_ACTION_PREFIX))
async def contact_registry_action_callback(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    payload = (callback.data or '')[len(_REGISTRY_ACTION_PREFIX):]
    parts = payload.split(':', 1)
    if len(parts) != 2:
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return
    nonce, action = parts
    allowed_actions = {'supplement', 'save', 'manual', 'cancel', 'retry'}
    if action not in allowed_actions:
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return
    validated = await _validated_registry_callback(
        callback=callback,
        state=state,
        config=config,
        allowed_states={
            ContactStates.registry_candidates.state,
            ContactStates.registry_detail_preview.state,
            ContactStates.registry_fallback.state,
        },
        nonce=nonce,
    )
    if validated is None or callback.message is None:
        return
    session, context = validated
    current_state = await state.get_state()
    state_actions = {
        ContactStates.registry_candidates.state: {'manual', 'cancel'},
        ContactStates.registry_detail_preview.state: {'supplement', 'save', 'manual', 'cancel'},
        ContactStates.registry_fallback.state: {'retry', 'manual', 'cancel'},
    }
    if action not in state_actions.get(current_state, set()):
        await callback.answer(_REGISTRY_STALE_MESSAGE, show_alert=True)
        return

    session = await _refresh_registry_activity(state=state, session=session)
    if action == 'cancel':
        await state.clear()
        await _clear_registry_keyboard(callback)
        await callback.message.answer('Vytvorenie kontaktu bolo zrušené.')
    elif action == 'manual':
        await _clear_registry_keyboard(callback)
        await _registry_manual_fallback(message=callback.message, state=state)
    elif action == 'retry':
        await _clear_registry_keyboard(callback)
        await _start_registry_search(
            message=callback.message,
            state=state,
            config=config,
            query=str(session.get('query') or ''),
            context=context,
            actor_telegram_id=callback.from_user.id,
        )
    elif action == 'supplement':
        draft = dict((await state.get_data()).get('contact_registry_draft') or {})
        await _clear_registry_keyboard(callback)
        if not validate_dic(str(draft.get('dic') or '')):
            await state.set_state(ContactStates.registry_required_dic)
            await callback.message.answer('Zadajte DIČ (10 číslic).')
        else:
            await state.set_state(ContactStates.registry_optional_email)
            await callback.message.answer('Zadajte email, pošlite "-" pre preskočenie alebo "vymazať" pre vyčistenie existujúcej hodnoty.')
    else:
        draft = dict((await state.get_data()).get('contact_registry_draft') or {})
        if not _registry_required_complete(draft):
            await callback.answer('Najprv doplňte povinné údaje.', show_alert=True)
            return
        await _clear_registry_keyboard(callback)
        await _enter_registry_final_confirmation(
            message=callback.message,
            state=state,
            config=config,
            actor_telegram_id=callback.from_user.id,
        )
    await callback.answer()


async def _ensure_registry_actor_context(message: Message, state: FSMContext, config: Config) -> bool:
    if message.from_user is None:
        return False
    try:
        await _registry_context_for_actor(
            actor_telegram_id=message.from_user.id,
            state=state,
            config=config,
        )
    except WorkspaceContextError:
        await state.clear()
        await message.answer('Business profil kontaktu už nie je dostupný.')
        return False
    return True


@router.message(ContactStates.registry_required_dic)
async def contact_registry_required_dic(message: Message, state: FSMContext, config: Config) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return
    if not await _ensure_registry_actor_context(message, state, config):
        return
    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer(_with_contact_recovery_hint('Neplatné DIČ. Zadajte 10 číslic.'))
        return
    data = await state.get_data()
    draft = dict(data.get('contact_registry_draft') or {})
    draft['dic'] = value
    await state.update_data(contact_registry_draft=draft)
    await state.set_state(ContactStates.registry_optional_email)
    await message.answer('Zadajte email, pošlite "-" pre preskočenie alebo "vymazať" pre vyčistenie existujúcej hodnoty.')


@router.message(ContactStates.registry_optional_email)
async def contact_registry_optional_email(message: Message, state: FSMContext, config: Config) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return
    if not await _ensure_registry_actor_context(message, state, config):
        return
    value = (message.text or '').strip()
    data = await state.get_data()
    draft = dict(data.get('contact_registry_draft') or {})
    if value == '-':
        draft['email_supplied'] = False
    elif value.casefold() == 'vymazať':
        draft['email'] = ''
        draft['email_supplied'] = True
    elif not validate_email(value):
        await message.answer(_with_contact_recovery_hint('Neplatný email. Skúste znova alebo pošlite "-".'))
        return
    else:
        draft['email'] = value
        draft['email_supplied'] = True
    await state.update_data(contact_registry_draft=draft)
    await state.set_state(ContactStates.registry_optional_iban)
    await message.answer('Zadajte IBAN, pošlite "-" pre preskočenie alebo "vymazať" pre vyčistenie existujúcej hodnoty.')


@router.message(ContactStates.registry_optional_iban)
async def contact_registry_optional_iban(message: Message, state: FSMContext, config: Config) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return
    if not await _ensure_registry_actor_context(message, state, config):
        return
    value = (message.text or '').strip()
    data = await state.get_data()
    draft = dict(data.get('contact_registry_draft') or {})
    if value == '-':
        draft['iban_supplied'] = False
    elif value.casefold() == 'vymazať':
        draft['iban'] = ''
        draft['iban_supplied'] = True
    elif not validate_contact_iban(value):
        await message.answer(_with_contact_recovery_hint('Neplatný IBAN. Skúste znova alebo pošlite "-".'))
        return
    else:
        draft['iban'] = normalize_contact_iban(value)
        draft['iban_supplied'] = True
    await state.update_data(contact_registry_draft=draft)
    await state.set_state(ContactStates.registry_optional_contact_person)
    await message.answer('Zadajte kontaktnú osobu, pošlite "-" pre preskočenie alebo "vymazať" pre vyčistenie existujúcej hodnoty.')


@router.message(ContactStates.registry_optional_contact_person)
async def contact_registry_optional_contact_person(message: Message, state: FSMContext, config: Config) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return
    if not await _ensure_registry_actor_context(message, state, config):
        return
    value = (message.text or '').strip()
    data = await state.get_data()
    draft = dict(data.get('contact_registry_draft') or {})
    if value == '-':
        draft['contact_person_supplied'] = False
    elif value.casefold() == 'vymazať':
        draft['contact_person'] = ''
        draft['contact_person_supplied'] = True
    else:
        draft['contact_person'] = value
        draft['contact_person_supplied'] = True
    session = dict(data.get(_REGISTRY_SESSION_KEY) or {})
    await state.update_data(contact_registry_draft=draft)
    await state.set_state(ContactStates.registry_detail_preview)
    await message.answer(
        _registry_preview_text(draft),
        reply_markup=_registry_preview_keyboard(str(session.get('nonce') or ''), can_save=True),
    )


@router.message(ContactStates.registry_final_confirm)
async def contact_registry_final_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return
    if canonical_decision is None:
        decision = await resolve_yes_no(
            context_name='contact_registry_confirm',
            user_input_text=message.text or '',
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    else:
        decision = canonical_decision if canonical_decision in {'yes', 'no', 'unknown'} else 'unknown'
    if decision == 'unknown':
        await message.answer(_with_contact_recovery_hint('Napíšte ano alebo nie.'))
        return
    if decision == 'no':
        await state.clear()
        await message.answer('Vytvorenie kontaktu bolo zrušené.')
        return
    if message.from_user is None:
        return
    try:
        context = await _registry_context_for_actor(
            actor_telegram_id=message.from_user.id,
            state=state,
            config=config,
        )
        result = RegistryContactSaveService(config.db_path).save(
            context,
            _registry_contact_draft(await state.get_data()),
        )
    except RegistryContactConflict:
        await state.clear()
        await message.answer('Údaje existujúcich kontaktov sú v konflikte. Nič som nezmenil.')
        return
    except (WorkspaceContextError, ValueError, RuntimeError):
        await state.clear()
        await message.answer('Kontakt sa nepodarilo bezpečne uložiť. Nič som nezmenil.')
        return
    await state.clear()
    verb = 'aktualizovaný' if result.mode == 'update' else 'uložený'
    await message.answer(f'Kontakt bol {verb}.')


@router.message(ContactStates.registry_candidates)
@router.message(ContactStates.registry_detail_preview)
@router.message(ContactStates.registry_fallback)
async def contact_registry_button_only(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return
    await message.answer(_with_contact_recovery_hint('Vyberte jednu z možností na tlačidlách.'))

@router.message(ContactStates.intake_missing)
async def contact_intake_missing(message: Message, state: FSMContext) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    await process_contact_missing_fields(
        message=message,
        state=state,
        user_text=message.text or '',
    )


@router.message(ContactStates.intake_confirm)
async def contact_intake_confirm(message: Message, state: FSMContext, config: Config) -> None:
    if not await _ensure_contact_session_active(message=message, state=state):
        return

    await process_contact_intake_confirm(
        message=message,
        state=state,
        config=config,
        answer_text=message.text or '',
    )


@router.message(lambda message: message.document is not None and not (message.text or '').startswith('/'))
async def contact_intake_from_document(message: Message, state: FSMContext, config: Config, bot) -> None:
    current_state = await state.get_state()
    if current_state is not None:
        return

    caption = (message.caption or '').strip()
    intent = await resolve_semantic_action(
        context_name='top_level_action',
        allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
        user_input_text=caption,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if intent != 'add_contact':
        await message.answer(
            'Dokument som nepriradil ku kontaktu. Ak chcete import kontaktu, '
            'napíšte napríklad: „pridaj kontakt“ a priložte dokument s popisom.'
        )
        return

    await state.clear()
    await state.set_state(ContactStates.source_after_name)
    await state.update_data(contact_company_hint=(_extract_company_hint(caption) or ''))
    await _process_source_after_name_step(message, state, config, bot)
