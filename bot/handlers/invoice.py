from __future__ import annotations

from datetime import date, timedelta
import json
import logging
from pathlib import Path
import re
from uuid import uuid4

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from bot.config import Config
from bot.handlers.contacts import start_add_contact_intake
from bot.handlers.supplier import start_add_service_alias_intake
from bot.services.contact_service import ContactLookupResult, ContactProfile, ContactService
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.llm_invoice_parser import LlmInvoicePayloadError, parse_invoice_phase2_payload
from bot.services.pdf_generator import (
    PdfInvoiceData,
    PdfInvoiceItem,
    generate_invoice_pdf,
    validate_item_detail_render_fit,
)
from bot.services.service_alias_service import ServiceAliasService
from bot.services.semantic_action_resolver import (
    resolve_bounded_confirmation_reply,
    resolve_invoice_date_normalization,
    resolve_semantic_action,
)
from bot.services.semantic_action_resolver import resolve_quantity_unit_price_pair
from bot.services.supplier_service import SupplierService
from bot.services.validation import parse_strict_date_dd_mm_yyyy

router = Router(name='invoice')
logger = logging.getLogger(__name__)


_CREATE_INVOICE_INTENT = 'create_invoice'
_EDIT_INVOICE_INTENT = 'edit_invoice'
_SEND_INVOICE_INTENT = 'send_invoice'
_ADD_CONTACT_INTENT = 'add_contact'
_ADD_SERVICE_ALIAS_INTENT = 'add_service_alias'
_UNKNOWN_INVOICE_INTENT = 'unknown'


class InvoiceStates(StatesGroup):
    waiting_input = State()
    waiting_service_clarification = State()
    waiting_slot_clarification = State()
    waiting_confirm = State()
    waiting_pdf_decision = State()
    waiting_edit_scope = State()
    waiting_edit_invoice_action = State()
    waiting_edit_item_target = State()
    waiting_edit_item_action = State()
    waiting_edit_invoice_number_value = State()
    waiting_edit_invoice_date_value = State()
    waiting_edit_service_value = State()
    waiting_edit_description_value = State()


_SLOT_SERVICE = 'service_term'
_SLOT_CUSTOMER = 'customer_name'
_SLOT_DELIVERY_DATE = 'delivery_date'
_SLOT_DUE_DAYS = 'due_days'
_SLOT_QUANTITY = 'quantity'
_SLOT_UNIT_PRICE = 'unit_price'
_SLOT_QUANTITY_UNIT_PRICE = 'quantity_unit_price_pair'
_SLOT_ITEMS = 'items'
_EDIT_ITEM_OPERATION_REPLACE_SERVICE = 'replace_service'
_EDIT_ITEM_OPERATION_REPLACE_MAIN_DESCRIPTION = 'replace_main_description'
_EDIT_ITEM_OPERATION_ADD_DETAILS = 'add_item_details'
_EDIT_ITEM_OPERATION_CLEAR_DETAILS = 'clear_item_details'
_EDIT_INVOICE_OPERATION_NUMBER = 'edit_invoice_number'
_EDIT_INVOICE_OPERATION_DATE = 'edit_invoice_date'
_EDIT_INVOICE_OPERATION_ISSUE_DATE = 'edit_invoice_issue_date'
_EDIT_INVOICE_OPERATION_DELIVERY_DATE = 'edit_invoice_delivery_date'
_EDIT_INVOICE_OPERATION_DUE_DATE = 'edit_invoice_due_date'
_EDIT_ITEM_OPERATION_UNKNOWN = 'unknown'
_INVOICE_NUMBER_PATTERN = re.compile(r'^(?:19|20)\d{6}$')
_ITEM_BOUNDARY_NUMBERED_MARKER_PATTERN = re.compile(
    r'(?:^|[\s,;:])'
    r'(?:'
    r'item'
    r'|polozka'
    r'|polo\u017eka'
    r'|pozicia'
    r'|poz\u00edcia'
    r'|pozitsiya'
    r'|pozitsiia'
    r'|\u043f\u043e\u0437\u0438\u0446\u0438\u044f'
    r'|\u043f\u043e\u0437\u0438\u0446\u0456\u044f'
    r'|\u043f\u043e\u043b\u043e\u0436\u043a\u0430'
    r')'
    r'(?:\s+(?:cislo|'
    r'\u010d\u00edslo|'
    r'number|no\.?|nr\.?|'
    r'\u043d\u043e\u043c\u0435\u0440'
    r'))?'
    r'\s+([1-3])(?=$|[\s,;:.\-])',
    re.IGNORECASE,
)

_SLOT_PROMPTS = {
    _SLOT_CUSTOMER: 'Nepodarilo sa jednoznačne určiť odberateľa. Spresnite názov firmy, prosím.',
    _SLOT_SERVICE: 'Nepodarilo sa jednoznačne určiť typ služby. Spresnite ho, prosím.',
    _SLOT_DELIVERY_DATE: 'Nepodarilo sa jednoznačne určiť dátum dodania. Spresnite ho, prosím.',
    _SLOT_DUE_DAYS: 'Nepodarilo sa jednoznačne určiť splatnosť. Zadajte počet dní, prosím.',
    _SLOT_QUANTITY: 'Nepodarilo sa jednoznačne určiť množstvo. Spresnite ho, prosím.',
    _SLOT_UNIT_PRICE: 'Nepodarilo sa jednoznačne určiť cenu. Spresnite ju, prosím.',
    _SLOT_QUANTITY_UNIT_PRICE: (
        'Uveďte množstvo a cenu za jednotku, napr. 3 po 1500 alebo 3 1500. '
        'Ak je množstvo 1, môžete zadať len cenu, napr. 1500.'
    ),
    _SLOT_ITEMS: (
        'Nie je jasné rozdelenie položiek alebo finančné údaje položiek. '
        'Napíšte položky jasne po riadkoch alebo oddelené čiarkou (max 3 položky).'
    ),
}


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    txt = str(value).strip()
    if not txt:
        return None
    try:
        return date.fromisoformat(txt)
    except ValueError:
        return None


def _parse_positive_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(str(value).replace(',', '.').strip())
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _resolve_contact_lookup(contact_service: ContactService, telegram_id: int, name: str) -> ContactLookupResult:
    return contact_service.resolve_contact_lookup(telegram_id, name)


def _normalize_semantic_lookup_key(value: str) -> str:
    lowered = value.casefold().strip()
    separators_normalized = re.sub(r'[^\w\sÀ-žЀ-ӿ]+', ' ', lowered, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', separators_normalized).strip()


async def _resolve_customer_candidate_bounded(
    *,
    contact_service: ContactService,
    telegram_id: int,
    candidate_text: str,
    config: Config,
    context_name: str,
    bounded_contact_names: list[str] | None = None,
) -> tuple[ContactProfile | None, list[str]]:
    if bounded_contact_names is None:
        contact_names = [contact.name for contact in contact_service.get_all_by_supplier(telegram_id)]
    else:
        contact_names = [name for name in bounded_contact_names if isinstance(name, str)]

    deduplicated_names: list[str] = []
    seen_names: set[str] = set()
    for name in contact_names:
        normalized_name = name.strip()
        if not normalized_name or normalized_name in seen_names:
            continue
        seen_names.add(normalized_name)
        deduplicated_names.append(normalized_name)

    if not deduplicated_names:
        return None, []

    normalized_candidate, compressed_candidate = contact_service.normalize_lookup_forms(candidate_text)
    for contact_name in deduplicated_names:
        contact_normalized, contact_compressed = contact_service.normalize_lookup_forms(contact_name)
        if (
            normalized_candidate
            and contact_normalized
            and normalized_candidate == contact_normalized
        ) or (
            compressed_candidate
            and contact_compressed
            and compressed_candidate == contact_compressed
        ):
            return contact_service.get_by_name(telegram_id, contact_name), deduplicated_names

    available_profiles = {
        contact.name: contact
        for contact in contact_service.get_all_by_supplier(telegram_id)
        if contact.name in deduplicated_names
    }
    option_descriptions = [
        {
            'value': contact_name,
            'description': (
                f'IČO: {profile.ico}, DIČ: {profile.dic}, email: {profile.email}'
                if (profile := available_profiles.get(contact_name)) is not None
                else ''
            ),
        }
        for contact_name in deduplicated_names
    ]

    canonical = await resolve_semantic_action(
        context_name=context_name,
        allowed_actions=deduplicated_names,
        user_input_text=candidate_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        auxiliary_context={
            'supplier_telegram_id': telegram_id,
            'option_descriptions': option_descriptions,
        },
    )
    if canonical not in available_profiles:
        return None, deduplicated_names

    return available_profiles[canonical], deduplicated_names


async def _resolve_service_alias_bounded(
    *,
    alias_service: ServiceAliasService,
    supplier_id: int,
    candidate_text: str,
    config: Config,
    context_name: str,
) -> tuple[str | None, str | None, list[str]]:
    mappings = alias_service.list_mappings(supplier_id)
    alias_to_display: dict[str, str] = {}
    normalized_alias_to_canonical: dict[str, str] = {}
    for mapping in mappings:
        canonical_alias = mapping.service_short_name.strip()
        display_name = mapping.service_display_name.strip()
        if not canonical_alias or not display_name:
            continue
        alias_to_display[canonical_alias] = display_name
        normalized_alias_to_canonical[_normalize_semantic_lookup_key(canonical_alias)] = canonical_alias

    allowed_aliases = sorted(alias_to_display.keys())
    if not allowed_aliases:
        return None, None, []

    normalized_candidate = _normalize_semantic_lookup_key(candidate_text)
    direct_match = normalized_alias_to_canonical.get(normalized_candidate)
    if direct_match is not None:
        return direct_match, alias_to_display[direct_match], allowed_aliases

    canonical = await resolve_semantic_action(
        context_name=context_name,
        allowed_actions=allowed_aliases,
        user_input_text=candidate_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        auxiliary_context={
            'supplier_id': supplier_id,
            'option_descriptions': [
                {'value': alias, 'description': alias_to_display[alias]} for alias in allowed_aliases
            ],
        },
    )
    if canonical not in alias_to_display:
        return None, None, allowed_aliases

    return canonical, alias_to_display[canonical], allowed_aliases


def _resolve_service_display_name(
    *,
    alias_service: ServiceAliasService,
    supplier_id: int,
    service_short_name: str,
    service_term_internal: str | None,
) -> str:
    raw_name = service_short_name.strip()
    raw_match = alias_service.resolve_service_display_name(supplier_id, raw_name)
    if raw_match:
        return raw_match

    internal = (service_term_internal or '').strip()
    candidates = [internal]
    if internal.endswith('a') and len(internal) > 1:
        candidates.append(f'{internal[:-1]}y')

    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_semantic_lookup_key(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        match = alias_service.resolve_service_display_name(supplier_id, candidate)
        if match:
            return match

    return raw_name


def _contact_lookup_feedback(result: ContactLookupResult) -> str:
    if result.state == 'multiple_candidates':
        top_names = ', '.join(contact.name for contact in result.candidates[:3])
        return (
            'Našiel som viac podobných kontaktov'
            + (f' ({top_names}). ' if top_names else '. ')
            + 'Prosím, upresnite názov odberateľa a skúste to znova.'
        )

    return (
        'Odberateľa sa nepodarilo spoľahlivo nájsť v lokálnej databáze kontaktov. '
        'Skontrolujte názov a skúste to znova. '
        'Ak kontakt ešte nemáte uložený, pridajte ho cez /contact.'
    )


def _format_preview(recognized_text: str | None, data: dict[str, object]) -> str:
    text_part = ''
    if recognized_text:
        text_part = f'<b>Rozpoznaný text:</b>\n{recognized_text}\n\n'
    invoice_number = str(data.get('invoice_number') or '-')

    items = data.get('items')
    if isinstance(items, list) and len(items) > 1:
        lines: list[str] = []
        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            detail_line = ''
            if item.get('item_description_raw'):
                detail_line = f'\n  Detail: {item.get("item_description_raw")}'
            lines.append(
                f'• Položka {idx}: {(item.get("service_display_name") or item.get("service_short_name") or "-")}\n'
                f'  Množstvo: {item.get("quantity")} {item.get("unit") or ""}\n'
                f'  Cena za m.j.: {float(item.get("unit_price") or 0.0):.2f} {data["currency"]}\n'
                f'  Spolu: {float(item.get("amount") or 0.0):.2f} {data["currency"]}'
                f'{detail_line}'
            )
        items_block = '\n'.join(lines)
        return (
            f'{text_part}'
            '<b>Náhľad faktúry:</b>\n'
            f'• Číslo faktúry: {invoice_number} (návrh)\n'
            f'• Odberateľ: {data["customer_name"]}\n'
            f'{items_block}\n'
            f'• Suma spolu: {data["amount"]:.2f} {data["currency"]}\n'
            f'• Dátum vystavenia: {data["issue_date"]}\n'
            f'• Dátum dodania: {data["delivery_date"]}\n'
            f'• Dátum splatnosti: {data["due_date"]}\n\n'
            'Napíšte: <b>schváliť</b>, <b>upraviť</b> alebo <b>zrušiť</b>.'
        )

    detail_part = ''
    if isinstance(items, list) and items and isinstance(items[0], dict) and items[0].get('item_description_raw'):
        detail_part = f'• Detail: {items[0]["item_description_raw"]}\n'
    return (
        f'{text_part}'
        '<b>Náhľad faktúry:</b>\n'
        f'• Číslo faktúry: {invoice_number} (návrh)\n'
        f'• Odberateľ: {data["customer_name"]}\n'
        f'• Plný názov služby: {data["service_display_name"]}\n'
        f'{detail_part}'
        f'• Množstvo: {data["quantity"]} {data["unit"] or ""}\n'
        f'• Cena za m.j.: {data["unit_price"]:.2f} {data["currency"]}\n'
        f'• Suma spolu: {data["amount"]:.2f} {data["currency"]}\n'
        f'• Dátum vystavenia: {data["issue_date"]}\n'
        f'• Dátum dodania: {data["delivery_date"]}\n'
        f'• Dátum splatnosti: {data["due_date"]}\n\n'
        'Napíšte: <b>schváliť</b>, <b>upraviť</b> alebo <b>zrušiť</b>.'
    )


def _draft_items(draft: dict[str, object]) -> list[dict[str, object]]:
    items = draft.get('items')
    if isinstance(items, list) and items:
        return [item for item in items if isinstance(item, dict)]
    return [
        {
            'item_index': 1,
            'service_short_name': draft.get('service_short_name'),
            'item_term_canonical_internal': draft.get('item_term_canonical_internal') or draft.get('service_short_name'),
            'service_display_name': draft.get('service_display_name'),
            'quantity': draft.get('quantity'),
            'unit_price': draft.get('unit_price'),
            'unit': draft.get('unit'),
            'amount': draft.get('amount'),
            'item_description_raw': None,
        }
    ]


def _sync_draft_from_items(draft: dict[str, object]) -> None:
    items = _draft_items(draft)
    draft['items'] = items
    if not items:
        return
    first_item = items[0]
    draft['service_short_name'] = first_item.get('service_short_name')
    draft['item_term_canonical_internal'] = (
        first_item.get('item_term_canonical_internal') or first_item.get('service_short_name')
    )
    draft['service_display_name'] = first_item.get('service_display_name') or first_item.get('service_short_name')
    draft['quantity'] = first_item.get('quantity')
    draft['unit_price'] = first_item.get('unit_price')
    draft['unit'] = first_item.get('unit')
    draft['amount'] = round(sum(float(item.get('amount') or 0.0) for item in items), 2)


def _draft_item_at_index(draft: dict[str, object], target_index: int) -> dict[str, object] | None:
    items = _draft_items(draft)
    if target_index < 1 or target_index > len(items):
        return None
    return items[target_index - 1]


def _draft_item_preview(draft: dict[str, object], target_index: int) -> str:
    item = _draft_item_at_index(draft, target_index)
    if item is None:
        return 'Položka na úpravu už nie je dostupná.'
    detail_part = item.get('item_description_raw') or '—'
    return (
        f'Úprava položky #{target_index} pre návrh faktúry {draft.get("invoice_number", "-")}:\n'
        f'• Služba: {item.get("service_display_name") or item.get("service_short_name")}\n'
        f'• Detail: {detail_part}'
    )


async def _show_updated_draft_preview(
    *,
    message: Message,
    state: FSMContext,
    draft: dict[str, object],
    success_text: str,
) -> None:
    _sync_draft_from_items(draft)
    await state.update_data(
        invoice_draft=draft,
        edit_stage=None,
        edit_target_item_index=None,
        edit_target_item_id=None,
        edit_item_action_mode=None,
        edit_invoice_date_operation=None,
    )
    await state.set_state(InvoiceStates.waiting_confirm)
    await message.answer(f'{success_text}\n\n{_format_preview(None, draft)}')


async def _resolve_invoice_edit_scope(*, config: Config, user_input_text: str) -> str:
    return await resolve_semantic_action(
        context_name='invoice_edit_scope_selection',
        allowed_actions=['invoice_level', 'item_level', _EDIT_ITEM_OPERATION_UNKNOWN],
        user_input_text=user_input_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )


async def _resolve_invoice_edit_action(*, config: Config, user_input_text: str) -> str:
    return await resolve_semantic_action(
        context_name='invoice_edit_invoice_action',
        allowed_actions=[
            _EDIT_INVOICE_OPERATION_NUMBER,
            _EDIT_INVOICE_OPERATION_ISSUE_DATE,
            _EDIT_INVOICE_OPERATION_DELIVERY_DATE,
            _EDIT_INVOICE_OPERATION_DUE_DATE,
            _EDIT_INVOICE_OPERATION_DATE,
            _EDIT_ITEM_OPERATION_UNKNOWN,
        ],
        user_input_text=user_input_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )


async def _resolve_item_target_index_bounded(
    *,
    config: Config,
    user_input_text: str,
    item_count: int,
    item_options: list[str] | None = None,
) -> int | None:
    allowed_targets = [str(index) for index in range(1, item_count + 1)]
    canonical = await resolve_semantic_action(
        context_name='invoice_edit_item_target_selection',
        allowed_actions=[*allowed_targets, _EDIT_ITEM_OPERATION_UNKNOWN],
        user_input_text=user_input_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        auxiliary_context={
            'item_count': item_count,
            'item_options': item_options or [],
        },
    )
    if canonical not in allowed_targets:
        if canonical.isdigit():
            return int(canonical)
        return None
    try:
        return int(canonical)
    except ValueError:
        return None


async def _resolve_item_edit_action(*, config: Config, user_input_text: str) -> str:
    return await resolve_semantic_action(
        context_name='invoice_edit_item_action',
        allowed_actions=[
            _EDIT_ITEM_OPERATION_REPLACE_SERVICE,
            _EDIT_ITEM_OPERATION_REPLACE_MAIN_DESCRIPTION,
            _EDIT_ITEM_OPERATION_ADD_DETAILS,
            _EDIT_ITEM_OPERATION_CLEAR_DETAILS,
            _EDIT_ITEM_OPERATION_UNKNOWN,
        ],
        user_input_text=user_input_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )


def _is_valid_invoice_number_for_edit(*, invoice_issue_date: str, invoice_number_candidate: str) -> bool:
    if not _INVOICE_NUMBER_PATTERN.fullmatch(invoice_number_candidate):
        return False
    issue_year = invoice_issue_date[:4]
    if not issue_year.isdigit():
        return False
    if not invoice_number_candidate.startswith(issue_year):
        return False
    return invoice_number_candidate[4:] != '0000'


def _parse_strict_issue_date_candidate(value: str) -> str | None:
    parsed = parse_strict_date_dd_mm_yyyy(value)
    if parsed is None:
        return None
    return parsed.isoformat()


def _invoice_date_prompt_for_operation(operation: str) -> str:
    if operation == _EDIT_INVOICE_OPERATION_ISSUE_DATE:
        return (
            'Napíšte alebo nadiktujte nový dátum vystavenia. '
            'Očakávaný výsledok bude uložený vo formáte DD.MM.RRRR.'
        )
    if operation == _EDIT_INVOICE_OPERATION_DELIVERY_DATE:
        return (
            'Napíšte alebo nadiktujte nový dátum dodania. '
            'Očakávaný výsledok bude uložený vo formáte DD.MM.RRRR.'
        )
    return (
        'Napíšte alebo nadiktujte nový dátum splatnosti. '
        'Očakávaný výsledok bude uložený vo formáte DD.MM.RRRR.'
    )


def _item_edit_actions_prompt() -> str:
    return (
        'Vyberte úpravu položky: napíšte `zmeniť službu`, `nový opis položky`, '
        '`pridať detaily k položke` alebo `vymazať detaily položky`.'
    )


def _extract_invoice_draft_from_phase2_payload(payload: dict) -> tuple[str, dict[str, object]]:
    vstup = payload.get('vstup') if isinstance(payload, dict) else {}
    biznis_sk = payload.get('biznis_sk') if isinstance(payload, dict) else {}

    raw_text = str((vstup or {}).get('povodny_text') or '').strip()
    singleton_item = {
        'item_name_raw': (biznis_sk or {}).get('polozka_povodna'),
        'service_term_sk': (biznis_sk or {}).get('termin_sluzby_sk'),
        'quantity': (biznis_sk or {}).get('mnozstvo'),
        'unit': (biznis_sk or {}).get('jednotka'),
        'amount': (biznis_sk or {}).get('suma'),
        'unit_price': (biznis_sk or {}).get('cena_za_jednotku'),
        'item_description_raw': None,
    }

    items_raw = (biznis_sk or {}).get('items')
    normalized_items: list[dict[str, object]] = []
    if isinstance(items_raw, list) and items_raw:
        for raw_item in items_raw:
            if not isinstance(raw_item, dict):
                continue
            normalized_items.append(
                {
                    'item_name_raw': raw_item.get('polozka_povodna'),
                    'service_term_sk': raw_item.get('termin_sluzby_sk'),
                    'quantity': raw_item.get('mnozstvo'),
                    'unit': raw_item.get('jednotka'),
                    'amount': raw_item.get('suma'),
                    'unit_price': raw_item.get('cena_za_jednotku'),
                    'item_description_raw': raw_item.get('item_description_raw'),
                }
            )
    if not normalized_items:
        normalized_items = [singleton_item]

    parsed_draft = {
        'customer_name': (biznis_sk or {}).get('odberatel_kandidat'),
        'item_name_raw': singleton_item['item_name_raw'],
        'service_term_sk': singleton_item['service_term_sk'],
        'quantity': singleton_item['quantity'],
        'unit': singleton_item['unit'],
        'amount': singleton_item['amount'],
        'unit_price': singleton_item['unit_price'],
        'items': normalized_items,
        'currency': (biznis_sk or {}).get('mena'),
        'delivery_date': (biznis_sk or {}).get('datum_dodania'),
        'due_days': (biznis_sk or {}).get('splatnost_dni'),
        'due_date': (biznis_sk or {}).get('datum_splatnosti'),
    }
    return raw_text, parsed_draft


_UNIT_PRICE_PATTERN = re.compile(
    r'(?P<qty>\d+(?:[.,]\d+)?)\s*(?:x|kr[aá]t|крат|razi|razy|раз|раза|рази|kusy|kus|ks|по)\s*(?:po|по)?\s*(?P<unit>\d+(?:[.,]\d+)?)',
    flags=re.IGNORECASE,
)
_AMOUNT_NUMBER_TOKEN_PATTERN = re.compile(r'(?<!\d)\d+(?:[.,]\d+)?(?!\d)')
_MULTIPLIER_HINT_PATTERN = re.compile(
    r'\b(?:x|kr[aá]t|крат|razi|razy|раз|раза|рази|kusy|kus|ks|po|по)\b',
    flags=re.IGNORECASE,
)
_EXPLICIT_YEAR_PATTERN = re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')
_DELIVERY_DAY_MONTH_PATTERN = re.compile(
    r'(?<!\d)(?P<day>0?[1-9]|[12]\d|3[01])\s*(?:[.\-/]\s*|\s+)'
    r'(?P<month>'
    r'janu[aá]r[a]?|jan'
    r'|febru[aá]r[a]?|feb'
    r'|marec|marca|mar'
    r'|apr[ií]l[a]?|apr'
    r'|m[aá]j[a]?'
    r'|j[uú]n[a]?'
    r'|j[uú]l[a]?'
    r'|august[a]?|aug'
    r'|sept(?:ember|embra)?|sep'
    r'|okt(?:[oó]ber|[oó]bra)?|okt'
    r'|nov(?:ember|embra)?|nov'
    r'|dec(?:ember|embra)?|dec'
    r'|январ[ья]|янв'
    r'|феврал[ья]|фев'
    r'|март[ае]?|марта|мар'
    r'|апрел[ья]|апр'
    r'|ма[йя]'
    r'|июн[ья]|июн'
    r'|июл[ья]|июл'
    r'|август[ае]?|авг'
    r'|сентябр[ья]|сен'
    r'|октябр[ья]|окт'
    r'|ноябр[ья]|ноя'
    r'|декабр[ья]|дек'
    r'|січня|січ'
    r'|лютого|лют'
    r'|березня|бер'
    r'|квітня|квіт'
    r'|травня|трав'
    r'|червня|черв'
    r'|липня|лип'
    r'|серпня|серп'
    r'|вересня|вер'
    r'|жовтня|жовт'
    r'|листопада|лист'
    r'|грудня|груд'
    r')\b',
    flags=re.IGNORECASE,
)
_MONTH_TOKEN_TO_NUMBER = {
    'januar': 1,
    'jan': 1,
    'februar': 2,
    'februara': 2,
    'feb': 2,
    'marec': 3,
    'marca': 3,
    'mar': 3,
    'april': 4,
    'aprila': 4,
    'apr': 4,
    'maj': 5,
    'maja': 5,
    'jun': 6,
    'juna': 6,
    'jul': 7,
    'jula': 7,
    'august': 8,
    'augusta': 8,
    'aug': 8,
    'september': 9,
    'septembra': 9,
    'sep': 9,
    'oktober': 10,
    'oktobra': 10,
    'okt': 10,
    'november': 11,
    'novembra': 11,
    'nov': 11,
    'december': 12,
    'decembra': 12,
    'dec': 12,
    'январь': 1,
    'января': 1,
    'янв': 1,
    'февраль': 2,
    'февраля': 2,
    'фев': 2,
    'март': 3,
    'марта': 3,
    'апрель': 4,
    'апреля': 4,
    'апр': 4,
    'май': 5,
    'мая': 5,
    'июнь': 6,
    'июня': 6,
    'июн': 6,
    'июль': 7,
    'июля': 7,
    'июл': 7,
    'август': 8,
    'августа': 8,
    'авг': 8,
    'сентябрь': 9,
    'сентября': 9,
    'сен': 9,
    'октябрь': 10,
    'октября': 10,
    'окт': 10,
    'ноябрь': 11,
    'ноября': 11,
    'ноя': 11,
    'декабрь': 12,
    'декабря': 12,
    'дек': 12,
    'січня': 1,
    'січ': 1,
    'лютого': 2,
    'лют': 2,
    'березня': 3,
    'бер': 3,
    'квітня': 4,
    'квіт': 4,
    'травня': 5,
    'трав': 5,
    'червня': 6,
    'черв': 6,
    'липня': 7,
    'лип': 7,
    'серпня': 8,
    'серп': 8,
    'вересня': 9,
    'вер': 9,
    'жовтня': 10,
    'жовт': 10,
    'листопада': 11,
    'лист': 11,
    'грудня': 12,
    'груд': 12,
}


def _parse_confident_unit_price_pattern(raw_text: str) -> tuple[float, float] | None:
    match = _UNIT_PRICE_PATTERN.search(raw_text)
    if not match:
        return None

    qty = _parse_positive_float(match.group('qty'))
    unit_price = _parse_positive_float(match.group('unit'))
    if qty is None or unit_price is None:
        return None
    return qty, unit_price


def _normalize_month_token(token: str) -> str:
    return (
        token.strip()
        .lower()
        .replace('á', 'a')
        .replace('í', 'i')
        .replace('ú', 'u')
        .replace('ó', 'o')
    )


def _has_explicit_year_near_day_month(raw_text: str, start: int, end: int) -> bool:
    local_window_start = max(0, start - 8)
    local_window_end = min(len(raw_text), end + 12)
    local_window = raw_text[local_window_start:local_window_end]
    return bool(_EXPLICIT_YEAR_PATTERN.search(local_window))


def _extract_day_month_without_explicit_year(raw_text: str) -> tuple[int, int] | None:
    match = _DELIVERY_DAY_MONTH_PATTERN.search(raw_text)
    if not match:
        return None
    if _has_explicit_year_near_day_month(raw_text, match.start(), match.end()):
        return None
    day = int(match.group('day'))
    month_token = _normalize_month_token(match.group('month'))
    month = _MONTH_TOKEN_TO_NUMBER.get(month_token)
    if month is None:
        return None
    return day, month


def _resolve_delivery_date(
    *,
    raw_text: str,
    issue_date_obj: date,
    llm_delivery_value: object,
) -> date:
    day_month_without_year = _extract_day_month_without_explicit_year(raw_text)
    parsed_delivery_date = _parse_date(llm_delivery_value)

    if day_month_without_year is None:
        return parsed_delivery_date or issue_date_obj

    anchor_day, anchor_month = day_month_without_year
    try:
        anchored_date = date(issue_date_obj.year, anchor_month, anchor_day)
    except ValueError as exc:
        raise ValueError('Neplatný dátum dodania vo vstupe.') from exc

    if parsed_delivery_date is None:
        return anchored_date

    if (parsed_delivery_date.month, parsed_delivery_date.day) != (anchor_month, anchor_day):
        raise ValueError('Nekonzistentný dátum dodania: AI payload nezodpovedá explicitnému dňu/mesiacu vo vstupe.')

    if parsed_delivery_date.year != issue_date_obj.year:
        return anchored_date

    return parsed_delivery_date


def _normalize_invoice_amount_semantics(
    *,
    raw_text: str,
    quantity_value: object,
    total_value: object,
    unit_price_value: object,
) -> tuple[float, float, float]:
    quantity = _parse_positive_float(quantity_value) or 1.0
    total_amount = _parse_positive_float(total_value)
    unit_price = _parse_positive_float(unit_price_value)

    explicit_pattern = _parse_confident_unit_price_pattern(raw_text)
    if explicit_pattern is not None:
        pattern_qty, pattern_unit_price = explicit_pattern
        expected_total = round(pattern_qty * pattern_unit_price, 2)
        if unit_price is not None and abs(unit_price - pattern_unit_price) > 0.01:
            raise ValueError('Konfliktná cena za jednotku (text vs. AI payload).')
        return pattern_qty, pattern_unit_price, expected_total

    has_multiplier_hint = bool(_MULTIPLIER_HINT_PATTERN.search(raw_text))
    if has_multiplier_hint and unit_price is None:
        raise ValueError('Nejednoznačná suma: vstup naznačuje násobenie, ale chýba spoľahlivá cena za jednotku.')

    if unit_price is not None and total_amount is not None:
        expected_total = round(quantity * unit_price, 2)
        if abs(expected_total - total_amount) > 0.01:
            raise ValueError('Nekonzistentné finančné údaje: množstvo × cena za jednotku != suma.')
        return quantity, unit_price, total_amount

    if unit_price is not None:
        return quantity, unit_price, round(quantity * unit_price, 2)

    if total_amount is None:
        raise ValueError('AI návrh je neúplný (chýba suma).')

    return quantity, round(total_amount / quantity, 2), total_amount


def _normalize_items_input(parsed_draft: dict[str, object]) -> list[dict[str, object]]:
    items_raw = parsed_draft.get('items')
    if isinstance(items_raw, list) and items_raw:
        normalized: list[dict[str, object]] = []
        for candidate in items_raw:
            if isinstance(candidate, dict):
                normalized.append(candidate)
        if normalized:
            return normalized
    return [
        {
            'item_name_raw': parsed_draft.get('item_name_raw'),
            'service_term_sk': parsed_draft.get('service_term_sk'),
            'quantity': parsed_draft.get('quantity'),
            'unit': parsed_draft.get('unit'),
            'amount': parsed_draft.get('amount'),
            'unit_price': parsed_draft.get('unit_price'),
            'item_description_raw': None,
        }
    ]


def _looks_like_item_boundary_split(text: str, *, expected_item_count: int) -> bool:
    normalized = f' {text.casefold()} '
    if ',' in text or ';' in text or '\n' in text:
        return True
    numbered_markers = {
        int(match.group(1))
        for match in _ITEM_BOUNDARY_NUMBERED_MARKER_PATTERN.finditer(text)
    }
    required_numbered_markers = max(1, expected_item_count - 1)
    if len(numbered_markers) >= required_numbered_markers and any(
        marker >= 2 for marker in numbered_markers
    ):
        return True
    has_conjunction_split = any(token in normalized for token in (' a ', ' и ', ' та ', ' plus '))
    if not has_conjunction_split:
        return False
    numeric_tokens = _AMOUNT_NUMBER_TOKEN_PATTERN.findall(text)
    return len(numeric_tokens) >= expected_item_count


def _emit_invoice_debug_log(
    *,
    config: Config,
    event: str,
    request_id: str,
    telegram_update_id: int | None,
    telegram_message_id: int | None,
    payload: dict[str, object],
) -> None:
    if not config.debug_invoice_transparency:
        return
    logger.info(
        json.dumps(
            {
                'event': event,
                'request_id': request_id,
                'telegram_update_id': telegram_update_id,
                'telegram_message_id': telegram_message_id,
                **payload,
            },
            ensure_ascii=False,
        )
    )


async def _build_and_store_preview(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    request_id: str,
    raw_text: str,
    parsed_draft: dict,
) -> None:
    message_id = getattr(message, 'message_id', None)
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        await state.clear()
        return

    customer_name = (parsed_draft.get('customer_name') or '').strip()
    if not customer_name:
        await _start_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            request_id=request_id,
            raw_text=raw_text,
            parsed_draft=parsed_draft,
            unresolved_slot=_SLOT_CUSTOMER,
        )
        return

    contact_service = ContactService(config.db_path)
    normalized_lookup, _compressed_lookup = contact_service.normalize_lookup_forms(customer_name)
    _emit_invoice_debug_log(
        config=config,
        event='invoice_lookup_before',
        request_id=request_id,
        telegram_update_id=getattr(message, 'update_id', None),
        telegram_message_id=message_id,
        payload={
            'lookup_raw_input': customer_name,
            'lookup_normalized_input': normalized_lookup,
        },
    )
    lookup_result = _resolve_contact_lookup(contact_service, message.from_user.id, customer_name)
    _emit_invoice_debug_log(
        config=config,
        event='invoice_lookup_after',
        request_id=request_id,
        telegram_update_id=getattr(message, 'update_id', None),
        telegram_message_id=message_id,
        payload={
            'lookup_state': lookup_result.state,
            'matched_contact_id': lookup_result.matched_contact.id if lookup_result.matched_contact else None,
            'candidate_count': len(lookup_result.candidates) if lookup_result.state == 'multiple_candidates' else None,
            'candidate_names': (
                [candidate.name for candidate in lookup_result.candidates]
                if lookup_result.state == 'multiple_candidates'
                else None
            ),
        },
    )
    if lookup_result.state in {'exact_match', 'normalized_match'} and lookup_result.matched_contact is not None:
        contact = lookup_result.matched_contact
    else:
        bounded_customer_candidates = (
            [candidate.name for candidate in lookup_result.candidates]
            if lookup_result.state == 'multiple_candidates'
            else [candidate.name for candidate in contact_service.get_all_by_supplier(message.from_user.id)]
        )
        resolved_contact, allowed_customer_candidates = await _resolve_customer_candidate_bounded(
            contact_service=contact_service,
            telegram_id=message.from_user.id,
            candidate_text=customer_name,
            config=config,
            context_name='invoice_customer_term_resolution',
            bounded_contact_names=bounded_customer_candidates,
        )
        if resolved_contact is None:
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_CUSTOMER,
                bounded_choices=allowed_customer_candidates[:5],
                debug_payload={
                    'lookup_feedback': _contact_lookup_feedback(lookup_result),
                    'lookup_state': lookup_result.state,
                },
                prefer_service_state=False,
                update_hint='Prosím, spresnite názov odberateľa a skúste to znova.',
            )
            return
        contact = resolved_contact

    if contact is None:
        await _start_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            request_id=request_id,
            raw_text=raw_text,
            parsed_draft=parsed_draft,
            unresolved_slot=_SLOT_CUSTOMER,
            bounded_choices=[],
        )
        return

    item_inputs = _normalize_items_input(parsed_draft)
    if len(item_inputs) > 3:
        await _start_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            request_id=request_id,
            raw_text=raw_text,
            parsed_draft=parsed_draft,
            unresolved_slot=_SLOT_ITEMS,
        )
        return
    if len(item_inputs) > 1 and not _looks_like_item_boundary_split(raw_text, expected_item_count=len(item_inputs)):
        await _start_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            request_id=request_id,
            raw_text=raw_text,
            parsed_draft=parsed_draft,
            unresolved_slot=_SLOT_ITEMS,
        )
        return

    normalized_items: list[dict[str, object]] = []
    total_amount = 0.0
    for item_index, item_input in enumerate(item_inputs, start=1):
        service_short_name_input = ((item_input.get('service_term_sk') or item_input.get('item_name_raw') or '').strip())
        if not service_short_name_input:
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_ITEMS if len(item_inputs) > 1 else _SLOT_SERVICE,
            )
            return

        if supplier.id is None:
            await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
            await state.clear()
            return

        service_short_name, service_display_name, allowed_aliases = await _resolve_service_alias_bounded(
            alias_service=ServiceAliasService(config.db_path),
            supplier_id=int(supplier.id),
            candidate_text=service_short_name_input,
            config=config,
            context_name='invoice_service_term_resolution',
        )
        if not service_short_name or not service_display_name:
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_ITEMS if len(item_inputs) > 1 else _SLOT_SERVICE,
                bounded_choices=allowed_aliases[:5],
            )
            return

        quantity_value = item_input.get('quantity')
        quantity_raw = _parse_positive_float(quantity_value)
        if quantity_value is not None and quantity_raw is None:
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_ITEMS if len(item_inputs) > 1 else _SLOT_QUANTITY,
            )
            return

        item_raw_hint = raw_text if len(item_inputs) == 1 else str(item_input.get('item_name_raw') or raw_text)
        total_raw = _parse_positive_float(item_input.get('amount'))
        unit_price_raw = _parse_positive_float(item_input.get('unit_price'))
        has_multiplier_hint = bool(_MULTIPLIER_HINT_PATTERN.search(item_raw_hint))
        explicit_amount_pattern = _parse_confident_unit_price_pattern(item_raw_hint)
        if (total_raw is None and unit_price_raw is None) or (
            has_multiplier_hint and unit_price_raw is None and explicit_amount_pattern is None
        ):
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_ITEMS if len(item_inputs) > 1 else _SLOT_QUANTITY_UNIT_PRICE,
            )
            return

        try:
            quantity, unit_price, amount = _normalize_invoice_amount_semantics(
                raw_text=item_raw_hint,
                quantity_value=quantity_value,
                total_value=item_input.get('amount'),
                unit_price_value=item_input.get('unit_price'),
            )
        except ValueError:
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_ITEMS if len(item_inputs) > 1 else _SLOT_QUANTITY_UNIT_PRICE,
            )
            return

        unit = (item_input.get('unit') or '').strip() or None
        total_amount = round(total_amount + amount, 2)
        normalized_items.append(
            {
                'item_index': item_index,
                'service_short_name': service_short_name,
                'item_term_canonical_internal': service_short_name,
                'service_display_name': service_display_name,
                'quantity': quantity,
                'unit_price': unit_price,
                'unit': unit,
                'amount': amount,
                'item_description_raw': item_input.get('item_description_raw'),
            }
        )

    if not normalized_items:
        await message.answer('AI návrh je neúplný (chýba položka alebo suma). Doplňte údaje a skúste to znova.')
        await state.clear()
        return

    first_item = normalized_items[0]
    currency = (parsed_draft.get('currency') or 'EUR').strip().upper() or 'EUR'

    issue_date_obj = date.today()
    try:
        delivery_date_obj = _resolve_delivery_date(
            raw_text=raw_text,
            issue_date_obj=issue_date_obj,
            llm_delivery_value=parsed_draft.get('delivery_date'),
        )
    except ValueError as exc:
        await _start_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            request_id=request_id,
            raw_text=raw_text,
            parsed_draft=parsed_draft,
            unresolved_slot=_SLOT_DELIVERY_DATE,
            debug_payload={'delivery_error': str(exc)},
        )
        return

    draft_due_days = parsed_draft.get('due_days')
    due_days = supplier.days_due
    if draft_due_days is not None:
        try:
            parsed_due = int(str(draft_due_days))
            if parsed_due > 0:
                due_days = parsed_due
            else:
                await _start_invoice_slot_clarification(
                    message=message,
                    state=state,
                    config=config,
                    request_id=request_id,
                    raw_text=raw_text,
                    parsed_draft=parsed_draft,
                    unresolved_slot=_SLOT_DUE_DAYS,
                )
                return
        except ValueError:
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_DUE_DAYS,
            )
            return

    due_date_obj = issue_date_obj + timedelta(days=due_days)
    invoice_service = InvoiceService(config.db_path)
    proposed_invoice_number = invoice_service.generate_next_invoice_number(issue_date_obj.year)

    normalized = {
        'raw_text': raw_text,
        'customer_name': contact.name,
        'contact_id': contact.id,
        'invoice_number': proposed_invoice_number,
        'invoice_number_manual_override': False,
        'service_short_name': first_item['service_short_name'],
        'item_term_canonical_internal': first_item['item_term_canonical_internal'],
        'service_display_name': first_item['service_display_name'],
        'quantity': first_item['quantity'],
        'unit_price': first_item['unit_price'],
        'unit': first_item['unit'],
        'amount': total_amount,
        'items': normalized_items,
        'currency': currency,
        'issue_date': issue_date_obj.isoformat(),
        'delivery_date': delivery_date_obj.isoformat(),
        'due_days': due_days,
        'due_date': due_date_obj.isoformat(),
    }
    _emit_invoice_debug_log(
        config=config,
        event='invoice_preview_before_save',
        request_id=request_id,
        telegram_update_id=getattr(message, 'update_id', None),
        telegram_message_id=message_id,
        payload={
            'original_text': raw_text,
            'final_contact_id': contact.id,
            'final_contact_name': contact.name,
            'service_short_name': first_item['service_short_name'],
            'service_display_name': first_item['service_display_name'],
            'service_term_canonical_internal': first_item['item_term_canonical_internal'],
            'item_count': len(normalized_items),
            'lookup_state': lookup_result.state,
        },
    )

    await state.update_data(invoice_draft=normalized)
    await state.set_state(InvoiceStates.waiting_confirm)
    await message.answer(_format_preview(raw_text if raw_text else None, normalized))


async def _start_service_slot_clarification(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    request_id: str,
    raw_text: str,
    parsed_draft: dict[str, object],
) -> None:
    await _start_invoice_slot_clarification(
        message=message,
        state=state,
        config=config,
        request_id=request_id,
        raw_text=raw_text,
        parsed_draft=parsed_draft,
        unresolved_slot=_SLOT_SERVICE,
        prefer_service_state=True,
    )


async def _start_invoice_slot_clarification(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    request_id: str,
    raw_text: str,
    parsed_draft: dict[str, object],
    unresolved_slot: str,
    bounded_choices: list[str] | None = None,
    debug_payload: dict[str, object] | None = None,
    prefer_service_state: bool = False,
    update_hint: str | None = None,
) -> None:
    partial_payload = {
        'request_id': request_id,
        'raw_text': raw_text,
        'parsed_draft': parsed_draft,
        'unresolved_slot': unresolved_slot,
    }
    if bounded_choices:
        partial_payload['bounded_choices'] = bounded_choices

    _emit_invoice_debug_log(
        config=config,
        event='invoice_slot_clarification_started',
        request_id=request_id,
        telegram_update_id=getattr(message, 'update_id', None),
        telegram_message_id=getattr(message, 'message_id', None),
        payload={
            'unresolved_slot': unresolved_slot,
            'raw_values': {
                'customer_name': parsed_draft.get('customer_name'),
                'service_term_sk': parsed_draft.get('service_term_sk'),
                'delivery_date': parsed_draft.get('delivery_date'),
                'due_days': parsed_draft.get('due_days'),
                'quantity': parsed_draft.get('quantity'),
                'unit_price': parsed_draft.get('unit_price'),
                'amount': parsed_draft.get('amount'),
            },
            'partial_draft_snapshot': parsed_draft,
            'clarification_entered': True,
            **(debug_payload or {}),
        },
    )

    await state.update_data(
        invoice_partial_draft=partial_payload
    )
    if prefer_service_state:
        await state.set_state(InvoiceStates.waiting_service_clarification)
    else:
        await state.set_state(InvoiceStates.waiting_slot_clarification)

    prompt = _SLOT_PROMPTS.get(unresolved_slot, 'Nepodarilo sa jednoznačne určiť údaj. Spresnite ho, prosím.')
    if bounded_choices:
        prompt = f'{prompt}\nMožnosti: {", ".join(bounded_choices)}.'
    if update_hint:
        prompt = f'{prompt}\n{update_hint}'
    await message.answer(prompt)


def _parse_date_clarification(value: str, *, issue_date_obj: date) -> str | None:
    raw = value.strip()
    if not raw:
        return None
    iso = _parse_date(raw)
    if iso is not None:
        return iso.isoformat()

    compact = raw.replace(' ', '')
    for separator in ('.', '/', '-'):
        parts = compact.split(separator)
        if len(parts) == 3:
            try:
                day = int(parts[0])
                month = int(parts[1])
                year = int(parts[2])
                return date(year, month, day).isoformat()
            except ValueError:
                return None
        if len(parts) == 2:
            try:
                day = int(parts[0])
                month = int(parts[1])
                return date(issue_date_obj.year, month, day).isoformat()
            except ValueError:
                return None
    return None


def _apply_slot_clarification(parsed_draft: dict[str, object], unresolved_slot: str, clarification_text: str) -> bool:
    normalized_text = clarification_text.strip()
    if unresolved_slot == _SLOT_SERVICE:
        return False
    if unresolved_slot == _SLOT_DELIVERY_DATE:
        parsed_date = _parse_date_clarification(normalized_text, issue_date_obj=date.today())
        if parsed_date is None:
            return False
        parsed_draft['delivery_date'] = parsed_date
        return True
    if unresolved_slot == _SLOT_DUE_DAYS:
        try:
            due_days = int(normalized_text)
        except ValueError:
            return False
        if due_days <= 0:
            return False
        parsed_draft['due_days'] = due_days
        return True
    if unresolved_slot in {_SLOT_QUANTITY, _SLOT_UNIT_PRICE}:
        parsed = _parse_positive_float(normalized_text)
        if parsed is None:
            return False
        target_key = 'quantity' if unresolved_slot == _SLOT_QUANTITY else 'unit_price'
        parsed_draft[target_key] = parsed
        return True
    return False


def _merge_item_clarification_into_draft(
    parsed_draft: dict[str, object],
    clarification_draft: dict[str, object],
) -> dict[str, object]:
    merged = dict(parsed_draft)
    clarified_items = _normalize_items_input(clarification_draft)
    if clarified_items:
        merged['items'] = clarified_items
        first_item = clarified_items[0]
        merged['item_name_raw'] = first_item.get('item_name_raw')
        merged['service_term_sk'] = first_item.get('service_term_sk')
        merged['quantity'] = first_item.get('quantity')
        merged['unit'] = first_item.get('unit')
        merged['amount'] = first_item.get('amount')
        merged['unit_price'] = first_item.get('unit_price')

    if clarification_draft.get('currency'):
        merged['currency'] = clarification_draft.get('currency')
    if clarification_draft.get('delivery_date'):
        merged['delivery_date'] = clarification_draft.get('delivery_date')
    if clarification_draft.get('due_days') is not None:
        merged['due_days'] = clarification_draft.get('due_days')
    if clarification_draft.get('due_date'):
        merged['due_date'] = clarification_draft.get('due_date')

    return merged


async def process_invoice_slot_clarification(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    clarification_text: str,
) -> None:
    state_data = await state.get_data()
    partial = state_data.get('invoice_partial_draft')
    if not isinstance(partial, dict):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    parsed_draft = partial.get('parsed_draft')
    unresolved_slot = str(partial.get('unresolved_slot') or '')
    if not isinstance(parsed_draft, dict) or not unresolved_slot:
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    if unresolved_slot == _SLOT_QUANTITY_UNIT_PRICE:
        resolution = await resolve_quantity_unit_price_pair(
            user_input_text=clarification_text,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
            clarification_context={
                'request_id': str(partial.get('request_id') or ''),
                'unresolved_slot': unresolved_slot,
                'raw_text': str(partial.get('raw_text') or ''),
            },
        )
        if resolution.get('canonical') != _SLOT_QUANTITY_UNIT_PRICE:
            await message.answer(_SLOT_PROMPTS[_SLOT_QUANTITY_UNIT_PRICE])
            return
        parsed_draft['quantity'] = float(resolution['quantity'])
        parsed_draft['unit_price'] = float(resolution['unit_price'])
    elif unresolved_slot == _SLOT_ITEMS:
        try:
            clarification_payload = await parse_invoice_phase2_payload(
                clarification_text,
                config.openai_api_key,
                config.openai_llm_model,
            )
            clarification_raw_text, clarification_draft = _extract_invoice_draft_from_phase2_payload(
                clarification_payload
            )
        except LlmInvoicePayloadError as exc:
            if exc.error_code in {
                'customer_unresolved',
                'items_shape_invalid',
                'items_count_exceeded',
                'items_service_unresolved',
            } and isinstance(exc.partial_payload, dict):
                clarification_raw_text, clarification_draft = _extract_invoice_draft_from_phase2_payload(
                    exc.partial_payload
                )
            else:
                await message.answer(_SLOT_PROMPTS[_SLOT_ITEMS])
                return

        clarification_items = _normalize_items_input(clarification_draft)
        if not clarification_items:
            await message.answer(_SLOT_PROMPTS[_SLOT_ITEMS])
            return

        parsed_draft = _merge_item_clarification_into_draft(parsed_draft, clarification_draft)
        raw_text_base = str(partial.get('raw_text') or '').strip()
        clarification_raw_text = clarification_raw_text.strip() or clarification_text.strip()
        combined_raw_text = (
            f'{raw_text_base}\n{clarification_raw_text}'.strip()
            if raw_text_base
            else clarification_raw_text
        )
        await _build_and_store_preview(
            message=message,
            state=state,
            config=config,
            request_id=str(partial.get('request_id') or uuid4()),
            raw_text=combined_raw_text,
            parsed_draft=parsed_draft,
        )
        return
    elif unresolved_slot == _SLOT_SERVICE:
        if message.from_user is None:
            await message.answer('Nepodarilo sa identifikovať používateľa.')
            return
        supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
        if supplier is None or supplier.id is None:
            await state.clear()
            await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
            return
        service_short_name, _service_display_name, allowed_aliases = await _resolve_service_alias_bounded(
            alias_service=ServiceAliasService(config.db_path),
            supplier_id=int(supplier.id),
            candidate_text=clarification_text,
            config=config,
            context_name='invoice_service_slot_clarification',
        )
        if service_short_name is None:
            prompt = _SLOT_PROMPTS[_SLOT_SERVICE]
            if allowed_aliases:
                prompt = f'{prompt}\nMožnosti: {", ".join(allowed_aliases[:5])}.'
            await message.answer(prompt)
            return
        parsed_draft['service_term_sk'] = service_short_name
        parsed_draft['item_name_raw'] = service_short_name
    elif unresolved_slot == _SLOT_CUSTOMER:
        if message.from_user is None:
            await message.answer('Nepodarilo sa identifikovať používateľa.')
            return
        contact_service = ContactService(config.db_path)
        bounded_customer_candidates = (
            partial.get('bounded_choices')
            if isinstance(partial.get('bounded_choices'), list)
            else None
        )
        resolved_contact, allowed_customer_candidates = await _resolve_customer_candidate_bounded(
            contact_service=contact_service,
            telegram_id=message.from_user.id,
            candidate_text=clarification_text,
            config=config,
            context_name='invoice_customer_slot_clarification',
            bounded_contact_names=bounded_customer_candidates,
        )
        if resolved_contact is None:
            prompt = _SLOT_PROMPTS[_SLOT_CUSTOMER]
            if allowed_customer_candidates:
                prompt = f'{prompt}\nMožnosti: {", ".join(allowed_customer_candidates[:5])}.'
            await message.answer(prompt)
            return
        parsed_draft['customer_name'] = resolved_contact.name
    elif not _apply_slot_clarification(parsed_draft, unresolved_slot, clarification_text):
        await message.answer(_SLOT_PROMPTS.get(unresolved_slot, 'Spresnite údaj, prosím.'))
        return

    await _build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id=str(partial.get('request_id') or uuid4()),
        raw_text=str(partial.get('raw_text') or clarification_text),
        parsed_draft=parsed_draft,
    )


async def process_invoice_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    invoice_text: str,
    request_id: str | None = None,
) -> None:
    flow_request_id = request_id or str(uuid4())
    message_id = getattr(message, 'message_id', None)

    top_level_intent = await resolve_semantic_action(
        context_name='top_level_action',
        allowed_actions=[
            _CREATE_INVOICE_INTENT,
            _ADD_CONTACT_INTENT,
            _ADD_SERVICE_ALIAS_INTENT,
            _SEND_INVOICE_INTENT,
            _EDIT_INVOICE_INTENT,
            _UNKNOWN_INVOICE_INTENT,
        ],
        user_input_text=invoice_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        action_hints={
            _CREATE_INVOICE_INTENT: {
                'meaning': 'user wants to create a new invoice draft',
                'not_this': ['edit existing invoice', 'send existing invoice'],
            },
            _ADD_SERVICE_ALIAS_INTENT: {
                'meaning': 'user wants to create a new reusable invoice item/service label',
                'positive_examples': [
                    'pridaj novú položku',
                    'pridaj novú službu',
                    'додай нову положку',
                    'додай нову службу',
                    'додай нову живність',
                    'предай новую живность',
                ],
                'not_this': ['create new invoice draft', 'edit existing invoice'],
            },
        },
    )
    if top_level_intent == _ADD_CONTACT_INTENT:
        await start_add_contact_intake(
            message=message,
            state=state,
            config=config,
        )
        return
    if top_level_intent == _ADD_SERVICE_ALIAS_INTENT:
        await start_add_service_alias_intake(
            message=message,
            state=state,
            config=config,
        )
        return
    if top_level_intent in {_EDIT_INVOICE_INTENT, _SEND_INVOICE_INTENT, _UNKNOWN_INVOICE_INTENT}:
        await message.answer(
            'Nerozumiem požadovanej akcii. Skúste to, prosím, povedať inak.'
        )
        await state.clear()
        return

    if not config.openai_api_key:
        await message.answer('Bot nie je nakonfigurovaný: chýba OPENAI_API_KEY.')
        await state.clear()
        return

    try:
        payload = await parse_invoice_phase2_payload(invoice_text, config.openai_api_key, config.openai_llm_model)
        payload_vstup = payload.get('vstup') if isinstance(payload, dict) else {}
        payload_biznis = payload.get('biznis_sk') if isinstance(payload, dict) else {}
        _emit_invoice_debug_log(
            config=config,
            event='invoice_phase2_payload_validated',
            request_id=flow_request_id,
            telegram_update_id=getattr(message, 'update_id', None),
            telegram_message_id=message_id,
            payload={
                'vstup_povodny_text': (payload_vstup or {}).get('povodny_text'),
                'biznis_sk_odberatel_kandidat': (payload_biznis or {}).get('odberatel_kandidat'),
                'biznis_sk_polozka_povodna': (payload_biznis or {}).get('polozka_povodna'),
                'biznis_sk_termin_sluzby_sk': (payload_biznis or {}).get('termin_sluzby_sk'),
            },
        )
        raw_text, parsed = _extract_invoice_draft_from_phase2_payload(payload)
    except LlmInvoicePayloadError as exc:
        payload_details = exc.details or {}
        _emit_invoice_debug_log(
            config=config,
            event='invoice_phase2_payload_invalid',
            request_id=flow_request_id,
            telegram_update_id=getattr(message, 'update_id', None),
            telegram_message_id=message_id,
            payload={
                'error': str(exc),
                'error_code': exc.error_code,
                'raw_biznis_sk_polozka_povodna': payload_details.get('raw_biznis_sk_polozka_povodna'),
                'raw_biznis_sk_termin_sluzby_sk': payload_details.get('raw_biznis_sk_termin_sluzby_sk'),
                'repaired_biznis_sk_polozka_povodna': payload_details.get('repaired_biznis_sk_polozka_povodna'),
                'repaired_service_term_canonical_internal': payload_details.get('repaired_service_term_canonical_internal'),
                'unresolved_slot': exc.error_code,
            },
        )
        if exc.error_code in {'service_term_unresolved', 'customer_unresolved', 'items_shape_invalid', 'items_count_exceeded', 'items_service_unresolved'} and isinstance(exc.partial_payload, dict):
            raw_text, parsed = _extract_invoice_draft_from_phase2_payload(exc.partial_payload)
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=flow_request_id,
                raw_text=raw_text or invoice_text,
                parsed_draft=parsed,
                unresolved_slot=(
                    _SLOT_SERVICE if exc.error_code == 'service_term_unresolved'
                    else _SLOT_CUSTOMER if exc.error_code == 'customer_unresolved'
                    else _SLOT_ITEMS
                ),
                prefer_service_state=exc.error_code == 'service_term_unresolved',
            )
            return
        logger.exception('LLM returned invalid Phase 2 invoice payload')
        await message.answer('AI návrh faktúry bol neplatný. Skúste vstup poslať znova.')
        await state.clear()
        return
    except Exception:
        logger.exception('LLM parsing failed in invoice flow')
        await message.answer('Nepodarilo sa spracovať návrh faktúry.')
        await state.clear()
        return

    await _build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id=flow_request_id,
        raw_text=raw_text or invoice_text,
        parsed_draft=parsed,
    )


async def process_invoice_service_clarification(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    clarification_text: str,
) -> None:
    state_data = await state.get_data()
    partial = state_data.get('invoice_partial_draft')
    if isinstance(partial, dict) and not partial.get('unresolved_slot'):
        partial['unresolved_slot'] = _SLOT_SERVICE
        await state.update_data(invoice_partial_draft=partial)
    await process_invoice_slot_clarification(
        message=message,
        state=state,
        config=config,
        clarification_text=clarification_text,
    )


def _create_invoice_items_from_draft(draft: dict[str, object]) -> list[CreateInvoiceItemPayload]:
    draft_items_raw = draft.get('items')
    normalized_items: list[CreateInvoiceItemPayload] = []
    if isinstance(draft_items_raw, list) and draft_items_raw:
        for item in draft_items_raw:
            if not isinstance(item, dict):
                continue
            normalized_items.append(
                CreateInvoiceItemPayload(
                    description_raw=str(item.get('service_short_name') or ''),
                    description_normalized=str(item.get('service_display_name') or item.get('service_short_name') or ''),
                    item_description_raw=(
                        str(item.get('item_description_raw')).strip()
                        if item.get('item_description_raw') is not None and str(item.get('item_description_raw')).strip()
                        else None
                    ),
                    quantity=float(item.get('quantity') or 1.0),
                    unit=(str(item.get('unit')).strip() if item.get('unit') else None),
                    unit_price=float(item.get('unit_price') or 0.0),
                    total_price=float(item.get('amount') or 0.0),
                )
            )
    if normalized_items:
        return normalized_items
    return [
        CreateInvoiceItemPayload(
            description_raw=str(draft['service_short_name']),
            description_normalized=str(draft['service_display_name']),
            item_description_raw=None,
            quantity=float(draft['quantity']),
            unit=str(draft['unit']) if draft['unit'] else None,
            unit_price=float(draft['unit_price']),
            total_price=float(draft['amount']),
        )
    ]


async def _start_invoice_draft_edit_flow(*, message: Message, state: FSMContext) -> None:
    state_data = await state.get_data()
    draft = state_data.get('invoice_draft')
    if not isinstance(draft, dict):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return
    items = _draft_items(draft)
    if not items:
        await state.clear()
        await message.answer('Návrh faktúry neobsahuje žiadne položky na úpravu.')
        return
    await state.update_data(
        edit_stage='draft',
        edit_invoice_id=None,
        edit_target_item_index=None,
        edit_target_item_id=None,
    )
    await state.set_state(InvoiceStates.waiting_edit_scope)
    await message.answer(
        f'Úprava návrhu faktúry {draft.get("invoice_number", "-")}. '
        'Vyberte rozsah úpravy: `faktúra` (číslo/dátum) alebo `položka`.'
    )


async def _finalize_invoice_draft(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    draft: dict[str, object],
) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        await state.clear()
        return

    contact_id = draft.get('contact_id')
    if contact_id is None:
        await message.answer('Kontakt nebol správne vyriešený. Spustite /invoice znova.')
        await state.clear()
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        await state.clear()
        return

    contact = ContactService(config.db_path).get_by_name_case_insensitive(
        message.from_user.id,
        str(draft['customer_name']),
    )
    if contact is None:
        await message.answer('Kontakt odberateľa sa nenašiel v databáze. Pridajte ho cez /contact.')
        await state.clear()
        return

    proposed_invoice_number = str(draft.get('invoice_number') or '').strip()
    if not proposed_invoice_number:
        proposed_invoice_number = InvoiceService(config.db_path).generate_next_invoice_number(
            int(str(draft['issue_date'])[:4])
        )
        draft['invoice_number'] = proposed_invoice_number
        await state.update_data(invoice_draft=draft)
    if not _is_valid_invoice_number_for_edit(
        invoice_issue_date=str(draft['issue_date']),
        invoice_number_candidate=proposed_invoice_number,
    ):
        await state.update_data(edit_stage='draft')
        await state.set_state(InvoiceStates.waiting_edit_invoice_number_value)
        await message.answer('Neplatné číslo faktúry. Zadajte číslo vo formáte RRRRNNNN.')
        return

    invoice_service = InvoiceService(config.db_path)
    if not invoice_service.is_invoice_number_available(invoice_number=proposed_invoice_number):
        await state.update_data(edit_stage='draft')
        await state.set_state(InvoiceStates.waiting_edit_invoice_number_value)
        await message.answer(
            f'Číslo faktúry {proposed_invoice_number} už existuje. '
            'Zadajte prosím iné číslo faktúry vo formáte RRRRNNNN.'
        )
        return

    invoice_id: int | None = None
    pdf_path = None
    try:
        normalized_items = _create_invoice_items_from_draft(draft)
        computed_total = round(sum(item.total_price for item in normalized_items), 2)
        draft_total = round(float(draft['amount']), 2)
        if abs(computed_total - draft_total) > 0.01:
            raise RuntimeError('Nekonzistentné finančné údaje v potvrdenom návrhu faktúry.')

        invoice_id = invoice_service.create_invoice_with_items(
            supplier_telegram_id=message.from_user.id,
            contact_id=int(contact_id),
            issue_date=str(draft['issue_date']),
            delivery_date=str(draft['delivery_date']),
            due_date=str(draft['due_date']),
            due_days=int(draft['due_days']),
            total_amount=float(draft['amount']),
            currency=str(draft['currency']),
            status='pripravena',
            items=normalized_items,
            invoice_number=proposed_invoice_number,
        )

        invoice = invoice_service.get_invoice_by_id(invoice_id)
        if invoice is None:
            raise RuntimeError('Invoice save succeeded, but invoice cannot be loaded.')

        items = invoice_service.get_items_by_invoice_id(invoice_id)
        pdf_path = config.storage_dir / 'invoices' / f'{invoice.invoice_number}.pdf'
        generate_invoice_pdf(
            target_path=pdf_path,
            supplier=supplier,
            customer=contact,
            invoice=PdfInvoiceData(
                invoice_number=invoice.invoice_number,
                issue_date=invoice.issue_date,
                delivery_date=invoice.delivery_date,
                due_date=invoice.due_date,
                variable_symbol=invoice.invoice_number,
                payment_method='bankový prevod',
                total_amount=float(invoice.total_amount),
                currency=invoice.currency,
            ),
            items=[
                PdfInvoiceItem(
                    description=item.description_normalized or item.description_raw,
                    detail=item.item_description_raw,
                    quantity=float(item.quantity),
                    unit=item.unit,
                    unit_price=float(item.unit_price),
                    total_price=float(item.total_price),
                )
                for item in items
            ],
        )
        invoice_service.save_pdf_path(invoice.id, str(pdf_path))
        await message.answer_document(
            FSInputFile(pdf_path),
            caption=f'PDF faktúra {invoice.invoice_number} bola vytvorená.',
        )
        await state.clear()
        await message.answer(f'Faktúra {invoice.invoice_number} bola vytvorená.')
    except Exception:
        logger.exception('Invoice finalization/pdf generation failed')
        db_cleanup_failed = False
        if invoice_id is not None:
            try:
                invoice_service.delete_invoice_with_items(invoice_id)
            except Exception:
                logger.exception('Cleanup after failed final PDF generation failed')
                db_cleanup_failed = True
        if pdf_path is not None:
            try:
                pdf_path.unlink(missing_ok=True)
            except Exception:
                logger.exception('PDF cleanup after failed final generation/sending failed')
        if db_cleanup_failed:
            await state.clear()
            await message.answer('Nepodarilo sa dokončiť zrušenie neúplnej faktúry. Spustite /invoice znova.')
            return
        await state.clear()
        await message.answer('Nepodarilo sa dokončiť vytvorenie PDF faktúry. Skúste to znova.')


async def process_invoice_preview_confirmation(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    confirmation_text: str,
) -> None:
    request_id = str(uuid4())
    state_before = await state.get_state()
    diagnostics: dict[str, object] = {}
    if config.debug_invoice_transparency:
        logger.info(
            json.dumps(
                {
                    'event': 'confirm_resolver_request',
                    'request_id': request_id,
                    'context_name': 'invoice_preview_confirmation',
                    'expected_reply_type': 'draft_review_decision',
                    'allowed_outputs': ['schvalit', 'upravit', 'zrusit', 'unknown'],
                    'user_input_text': confirmation_text,
                },
                ensure_ascii=False,
            )
        )
    answer = await resolve_bounded_confirmation_reply(
        context_name='invoice_preview_confirmation',
        expected_reply_type='draft_review_decision',
        allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
        user_input_text=confirmation_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        diagnostics=diagnostics,
    )
    if config.debug_invoice_transparency:
        logger.info(
            json.dumps(
                {
                    'event': 'confirm_resolver_response',
                    'request_id': request_id,
                    'raw_model_output': diagnostics.get('raw_model_output'),
                    'normalized_output': diagnostics.get('normalized_output', answer),
                    'fallback_used': bool(diagnostics.get('fallback_used', False)),
                    'fallback_output': diagnostics.get('fallback_output'),
                },
                ensure_ascii=False,
            )
        )
    if answer == 'unknown':
        if config.debug_invoice_transparency:
            logger.info(
                json.dumps(
                    {
                        'event': 'confirm_unknown_contract_gap',
                        'request_id': request_id,
                        'current_state': state_before,
                        'context_name': 'invoice_preview_confirmation',
                        'expected_reply_type': 'draft_review_decision',
                        'allowed_outputs': ['schvalit', 'upravit', 'zrusit', 'unknown'],
                        'user_input_text': confirmation_text,
                        'raw_model_output': diagnostics.get('raw_model_output'),
                        'normalized_output': diagnostics.get('normalized_output', answer),
                        'fallback_used': bool(diagnostics.get('fallback_used', False)),
                        'fallback_output': diagnostics.get('fallback_output'),
                    },
                    ensure_ascii=False,
                )
            )
            logger.info(
                json.dumps(
                    {
                        'event': 'confirm_branch_decision',
                        'request_id': request_id,
                        'final_answer': answer,
                        'state_before': state_before,
                        'branch_taken': 'unknown',
                    },
                    ensure_ascii=False,
                )
            )
        await message.answer('Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.')
        return

    if answer == 'zrusit':
        if config.debug_invoice_transparency:
            logger.info(
                json.dumps(
                    {
                        'event': 'confirm_branch_decision',
                        'request_id': request_id,
                        'final_answer': answer,
                        'state_before': state_before,
                        'branch_taken': 'draft_cancel',
                    },
                    ensure_ascii=False,
                )
            )
        await state.clear()
        await message.answer('Návrh faktúry bol zrušený.')
        return

    state_data = await state.get_data()
    draft = state_data.get('invoice_draft')
    if not isinstance(draft, dict):
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        await state.clear()
        return

    if answer == 'upravit':
        if config.debug_invoice_transparency:
            logger.info(
                json.dumps(
                    {
                        'event': 'confirm_branch_decision',
                        'request_id': request_id,
                        'final_answer': answer,
                        'state_before': state_before,
                        'branch_taken': 'draft_edit',
                    },
                    ensure_ascii=False,
                )
            )
        await _start_invoice_draft_edit_flow(message=message, state=state)
        return

    if config.debug_invoice_transparency:
        logger.info(
            json.dumps(
                {
                    'event': 'confirm_branch_decision',
                    'request_id': request_id,
                    'final_answer': answer,
                    'state_before': state_before,
                    'branch_taken': 'draft_finalize',
                },
                ensure_ascii=False,
            )
        )
    await _finalize_invoice_draft(message=message, state=state, config=config, draft=draft)


async def process_invoice_postpdf_decision(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    request_id = str(uuid4())
    state_before = await state.get_state()
    diagnostics: dict[str, object] = {}
    if config.debug_invoice_transparency:
        logger.info(
            json.dumps(
                {
                    'event': 'approval_resolver_request',
                    'request_id': request_id,
                    'context_name': 'invoice_postpdf_decision',
                    'expected_reply_type': 'postpdf_decision',
                    'allowed_outputs': ['schvalit', 'upravit', 'zrusit', 'unknown'],
                    'user_input_text': decision_text,
                },
                ensure_ascii=False,
            )
        )
    answer = await resolve_bounded_confirmation_reply(
        context_name='invoice_postpdf_decision',
        expected_reply_type='postpdf_decision',
        allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        diagnostics=diagnostics,
    )
    if config.debug_invoice_transparency:
        logger.info(
            json.dumps(
                {
                    'event': 'approval_resolver_response',
                    'request_id': request_id,
                    'raw_model_output': diagnostics.get('raw_model_output'),
                    'normalized_output': diagnostics.get('normalized_output', answer),
                    'fallback_used': bool(diagnostics.get('fallback_used', False)),
                    'fallback_output': diagnostics.get('fallback_output'),
                },
                ensure_ascii=False,
            )
        )
    if answer == 'unknown':
        if config.debug_invoice_transparency:
            logger.info(
                json.dumps(
                    {
                        'event': 'approval_unknown_contract_gap',
                        'request_id': request_id,
                        'current_state': state_before,
                        'context_name': 'invoice_postpdf_decision',
                        'expected_reply_type': 'postpdf_decision',
                        'allowed_outputs': ['schvalit', 'upravit', 'zrusit', 'unknown'],
                        'user_input_text': decision_text,
                        'raw_model_output': diagnostics.get('raw_model_output'),
                        'normalized_output': diagnostics.get('normalized_output', answer),
                        'fallback_used': bool(diagnostics.get('fallback_used', False)),
                        'fallback_output': diagnostics.get('fallback_output'),
                    },
                    ensure_ascii=False,
                )
            )
            logger.info(
                json.dumps(
                    {
                        'event': 'approval_branch_decision',
                        'request_id': request_id,
                        'final_answer': answer,
                        'invoice_id': None,
                        'state_before': state_before,
                        'branch_taken': 'unknown',
                    },
                    ensure_ascii=False,
                )
            )
        await message.answer('Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.')
        return

    state_data = await state.get_data()
    invoice_id = state_data.get('last_invoice_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    pdf_path_value = state_data.get('last_pdf_path')
    pdf_path = None
    if isinstance(pdf_path_value, str) and pdf_path_value.strip():
        pdf_path = Path(pdf_path_value)

    if answer == 'schvalit':
        if config.debug_invoice_transparency:
            logger.info(
                json.dumps(
                    {
                        'event': 'approval_branch_decision',
                        'request_id': request_id,
                        'final_answer': answer,
                        'invoice_id': invoice_id,
                        'state_before': state_before,
                        'branch_taken': 'schvalit',
                    },
                    ensure_ascii=False,
                )
            )
        try:
            InvoiceService(config.db_path).update_invoice_status(invoice_id, 'pripravena')
        except Exception:
            logger.exception('Invoice status update failed')
            await state.clear()
            await message.answer('Nepodarilo sa potvrdiť faktúru.')
            return
        await state.clear()
        await message.answer('Faktúra bola potvrdená.')
        return

    if answer == 'upravit':
        if config.debug_invoice_transparency:
            logger.info(
                json.dumps(
                    {
                        'event': 'approval_branch_decision',
                        'request_id': request_id,
                        'final_answer': answer,
                        'invoice_id': invoice_id,
                        'state_before': state_before,
                        'branch_taken': 'upravit',
                    },
                    ensure_ascii=False,
                )
            )
        await start_invoice_edit_flow(
            message=message,
            state=state,
            config=config,
            invoice_id=invoice_id,
        )
        return

    if config.debug_invoice_transparency:
        logger.info(
            json.dumps(
                {
                    'event': 'approval_branch_decision',
                    'request_id': request_id,
                    'final_answer': answer,
                    'invoice_id': invoice_id,
                    'state_before': state_before,
                    'branch_taken': 'zrusit',
                },
                ensure_ascii=False,
            )
        )
    try:
        InvoiceService(config.db_path).delete_invoice_with_items(invoice_id)
    except Exception:
        logger.exception('Invoice cleanup failed')
        await state.clear()
        await message.answer('Nepodarilo sa zrušiť faktúru.')
        return
    if pdf_path is not None:
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            logger.exception('PDF cleanup after cancel/edit failed')

    await state.clear()
    await message.answer('Faktúra bola zrušená. Číslo faktúry nebolo finálne potvrdené.')


def _format_item_edit_preview(invoice_number: str, item, item_index: int) -> str:
    detail_part = item.item_description_raw or '—'
    return (
        f'Úprava položky #{item_index} pre faktúru {invoice_number}:\n'
        f'• Služba: {item.description_normalized or item.description_raw}\n'
        f'• Detail: {detail_part}'
    )


def _resolve_target_item_from_index(*, invoice_items, target_item_index: int):
    if target_item_index < 1 or target_item_index > len(invoice_items):
        return None
    return invoice_items[target_item_index - 1]


async def _rebuild_pdf_for_existing_invoice(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    invoice_id: int,
) -> bool:
    if message.from_user is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return False

    invoice_service = InvoiceService(config.db_path)
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
        return False

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None:
        await state.clear()
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        return False

    contact = ContactService(config.db_path).get_by_id(invoice.contact_id)
    if contact is None:
        await state.clear()
        await message.answer('Kontakt odberateľa sa nenašiel v databáze.')
        return False

    items = invoice_service.get_items_by_invoice_id(invoice_id)
    pdf_path = config.storage_dir / 'invoices' / f'{invoice.invoice_number}.pdf'
    try:
        generate_invoice_pdf(
            target_path=pdf_path,
            supplier=supplier,
            customer=contact,
            invoice=PdfInvoiceData(
                invoice_number=invoice.invoice_number,
                issue_date=invoice.issue_date,
                delivery_date=invoice.delivery_date,
                due_date=invoice.due_date,
                variable_symbol=invoice.invoice_number,
                payment_method='bankový prevod',
                total_amount=float(invoice.total_amount),
                currency=invoice.currency,
            ),
            items=[
                PdfInvoiceItem(
                    description=item.description_normalized or item.description_raw,
                    detail=item.item_description_raw,
                    quantity=float(item.quantity),
                    unit=item.unit,
                    unit_price=float(item.unit_price),
                    total_price=float(item.total_price),
                )
                for item in items
            ],
        )
        invoice_service.save_pdf_path(invoice.id, str(pdf_path))
        await message.answer_document(
            FSInputFile(pdf_path),
            caption=f'Aktualizovaná PDF faktúra {invoice.invoice_number} je pripravená na kontrolu.',
        )
        await state.set_state(InvoiceStates.waiting_pdf_decision)
        await state.update_data(
            last_invoice_id=invoice.id,
            last_invoice_number=invoice.invoice_number,
            last_pdf_path=str(pdf_path),
        )
    except Exception:
        logger.exception('Invoice PDF rebuild failed after edit')
        await state.clear()
        await message.answer('Nepodarilo sa aktualizovať PDF faktúru po úprave.')
        return False

    return True


async def _send_post_edit_approval_prompt(*, message: Message, state: FSMContext, success_text: str) -> None:
    await state.set_state(InvoiceStates.waiting_pdf_decision)
    await message.answer(f'{success_text} Napíšte: schváliť, upraviť alebo zrušiť.')


async def start_invoice_edit_flow(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    invoice_id: int,
) -> None:
    invoice_service = InvoiceService(config.db_path)
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return
    items = invoice_service.get_items_by_invoice_id(invoice_id)
    if not items:
        await state.clear()
        await message.answer('Faktúra neobsahuje žiadne položky na úpravu.')
        return

    await state.update_data(
        edit_stage='persisted',
        edit_invoice_id=invoice_id,
        edit_target_item_index=None,
        edit_target_item_id=None,
    )
    await state.set_state(InvoiceStates.waiting_edit_scope)
    await message.answer(
        f'Úprava faktúry {invoice.invoice_number}. '
        'Vyberte rozsah úpravy: `faktúra` (číslo/dátum) alebo `položka`.'
    )


@router.message(Command('invoice'))
async def cmd_invoice(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(InvoiceStates.waiting_input)
    await message.answer(
        'Pošlite text faktúry (odberateľ, položka, suma, prípadne dátum dodania). '\
        'Potom vám ukážem náhľad pred uložením.'
    )


@router.message(InvoiceStates.waiting_input)
async def invoice_input(message: Message, state: FSMContext, config: Config) -> None:
    text = (message.text or '').strip()
    if not text:
        await message.answer('Pošlite prosím textový vstup pre návrh faktúry.')
        return

    await process_invoice_text(message=message, state=state, config=config, invoice_text=text)


@router.message(InvoiceStates.waiting_confirm)
async def invoice_confirm(message: Message, state: FSMContext, config: Config) -> None:
    await process_invoice_preview_confirmation(
        message=message,
        state=state,
        config=config,
        confirmation_text=(message.text or ''),
    )


@router.message(InvoiceStates.waiting_service_clarification)
async def invoice_service_clarification(message: Message, state: FSMContext, config: Config) -> None:
    await process_invoice_service_clarification(
        message=message,
        state=state,
        config=config,
        clarification_text=(message.text or ''),
    )


@router.message(InvoiceStates.waiting_slot_clarification)
async def invoice_slot_clarification(message: Message, state: FSMContext, config: Config) -> None:
    await process_invoice_slot_clarification(
        message=message,
        state=state,
        config=config,
        clarification_text=(message.text or ''),
    )


@router.message(InvoiceStates.waiting_pdf_decision)
async def invoice_pdf_decision(message: Message, state: FSMContext, config: Config) -> None:
    await process_invoice_postpdf_decision(
        message=message,
        state=state,
        config=config,
        decision_text=(message.text or ''),
    )


@router.message(InvoiceStates.waiting_edit_item_target)
async def invoice_edit_item_target(message: Message, state: FSMContext, config: Config) -> None:
    raw_value = (message.text or '').strip()

    state_data = await state.get_data()
    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        if not isinstance(draft, dict):
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return
        items = _draft_items(draft)
        option_descriptions = [
            str(item.get('service_display_name') or item.get('service_short_name') or '')
            for item in items
        ]
        target_index = await _resolve_item_target_index_bounded(
            config=config,
            user_input_text=raw_value,
            item_count=len(items),
            item_options=option_descriptions,
        )
        if target_index is None:
            await message.answer('Prosím, spresnite číslo položky, ktorú chcete upraviť (napr. 1 alebo 2).')
            return
        if _draft_item_at_index(draft, target_index) is None:
            await message.answer('Taká položka neexistuje. Zadajte prosím platné číslo položky (napr. 1 alebo 2).')
            return
        await state.update_data(edit_target_item_index=target_index, edit_target_item_id=target_index)
        await state.set_state(InvoiceStates.waiting_edit_item_action)
        await message.answer(_draft_item_preview(draft, target_index) + f'\n\n{_item_edit_actions_prompt()}')
        return

    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_service = InvoiceService(config.db_path)
    items = invoice_service.get_items_by_invoice_id(invoice_id)
    option_descriptions = [item.description_normalized or item.description_raw for item in items]
    target_index = await _resolve_item_target_index_bounded(
        config=config,
        user_input_text=raw_value,
        item_count=len(items),
        item_options=option_descriptions,
    )
    if target_index is None:
        await message.answer('Prosím, spresnite číslo položky, ktorú chcete upraviť (napr. 1 alebo 2).')
        return

    target_item = _resolve_target_item_from_index(invoice_items=items, target_item_index=target_index)
    if target_item is None:
        await message.answer('Taká položka neexistuje. Zadajte prosím platné číslo položky (napr. 1 alebo 2).')
        return

    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
        return

    await state.update_data(edit_target_item_index=target_index, edit_target_item_id=target_item.id)
    await state.set_state(InvoiceStates.waiting_edit_item_action)
    await message.answer(
        _format_item_edit_preview(invoice.invoice_number, target_item, target_index)
        + f'\n\n{_item_edit_actions_prompt()}',
    )


@router.message(InvoiceStates.waiting_edit_scope)
async def invoice_edit_scope(message: Message, state: FSMContext, config: Config) -> None:
    scope = await _resolve_invoice_edit_scope(config=config, user_input_text=(message.text or ''))
    if scope == _EDIT_ITEM_OPERATION_UNKNOWN:
        await message.answer(
            'Prosím, vyberte rozsah úpravy: `faktúra` alebo `položka`.'
        )
        return

    state_data = await state.get_data()
    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        if not isinstance(draft, dict):
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return
        if scope == 'invoice_level':
            await state.set_state(InvoiceStates.waiting_edit_invoice_action)
            await message.answer(
                f'Úprava na úrovni návrhu faktúry {draft.get("invoice_number", "-")}. '
                'Napíšte: `upraviť číslo faktúry`, `upraviť dátum vystavenia`, '
                '`upraviť dátum dodania` alebo `upraviť dátum splatnosti`.'
            )
            return
        items = _draft_items(draft)
        if not items:
            await state.clear()
            await message.answer('Návrh faktúry neobsahuje žiadne položky na úpravu.')
            return
        if len(items) == 1:
            await state.update_data(edit_target_item_index=1, edit_target_item_id=1)
            await state.set_state(InvoiceStates.waiting_edit_item_action)
            await message.answer(_draft_item_preview(draft, 1) + f'\n\n{_item_edit_actions_prompt()}')
            return
        await state.update_data(edit_target_item_index=None, edit_target_item_id=None)
        await state.set_state(InvoiceStates.waiting_edit_item_target)
        await message.answer(
            f'Návrh faktúry {draft.get("invoice_number", "-")} má viac položiek. '
            'Napíšte číslo položky, ktorú chcete upraviť (napr. 1, 2, 3).'
        )
        return

    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_service = InvoiceService(config.db_path)
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
        return

    if scope == 'invoice_level':
        await state.set_state(InvoiceStates.waiting_edit_invoice_action)
        await message.answer(
            f'Úprava na úrovni faktúry {invoice.invoice_number}. '
            'Napíšte: `upraviť číslo faktúry`, `upraviť dátum vystavenia`, '
            '`upraviť dátum dodania` alebo `upraviť dátum splatnosti`.'
        )
        return

    items = invoice_service.get_items_by_invoice_id(invoice_id)
    if not items:
        await state.clear()
        await message.answer('Faktúra neobsahuje žiadne položky na úpravu.')
        return

    if len(items) == 1:
        await state.update_data(edit_target_item_index=1, edit_target_item_id=items[0].id)
        await state.set_state(InvoiceStates.waiting_edit_item_action)
        await message.answer(
            _format_item_edit_preview(invoice.invoice_number, items[0], 1)
            + f'\n\n{_item_edit_actions_prompt()}',
        )
        return

    await state.update_data(edit_target_item_index=None, edit_target_item_id=None)
    await state.set_state(InvoiceStates.waiting_edit_item_target)
    await message.answer(
        f'Faktúra {invoice.invoice_number} má viac položiek. '
        'Napíšte číslo položky, ktorú chcete upraviť (napr. 1, 2, 3).'
    )


@router.message(InvoiceStates.waiting_edit_invoice_action)
async def invoice_edit_invoice_action(message: Message, state: FSMContext, config: Config) -> None:
    operation = await _resolve_invoice_edit_action(config=config, user_input_text=(message.text or ''))
    if operation == _EDIT_ITEM_OPERATION_UNKNOWN:
        await message.answer(
            'Prosím, napíšte `upraviť číslo faktúry`, `upraviť dátum vystavenia`, '
            '`upraviť dátum dodania` alebo `upraviť dátum splatnosti`.'
        )
        return

    state_data = await state.get_data()
    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        if not isinstance(draft, dict):
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return
        if operation == _EDIT_INVOICE_OPERATION_NUMBER:
            await state.set_state(InvoiceStates.waiting_edit_invoice_number_value)
            await message.answer(
                f'Aktuálne navrhované číslo faktúry je {draft.get("invoice_number", "-")}. '
                'Napíšte nové číslo faktúry vo formáte RRRRNNNN.'
            )
            return
        if operation == _EDIT_INVOICE_OPERATION_DATE:
            await message.answer('Ktorý dátum chcete upraviť: vystavenia, dodania alebo splatnosti?')
            return
        if operation not in {
            _EDIT_INVOICE_OPERATION_ISSUE_DATE,
            _EDIT_INVOICE_OPERATION_DELIVERY_DATE,
            _EDIT_INVOICE_OPERATION_DUE_DATE,
        }:
            await message.answer(
                'Prosím, napíšte `upraviť číslo faktúry`, `upraviť dátum vystavenia`, '
                '`upraviť dátum dodania` alebo `upraviť dátum splatnosti`.'
            )
            return
        await state.update_data(edit_invoice_date_operation=operation)
        await state.set_state(InvoiceStates.waiting_edit_invoice_date_value)
        await message.answer(_invoice_date_prompt_for_operation(operation))
        return

    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return
    invoice = InvoiceService(config.db_path).get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
        return

    if operation == _EDIT_INVOICE_OPERATION_NUMBER:
        await state.set_state(InvoiceStates.waiting_edit_invoice_number_value)
        await message.answer(
            f'Aktuálne číslo faktúry je {invoice.invoice_number}. '
            'Napíšte nové číslo faktúry vo formáte RRRRNNNN.'
        )
        return

    if operation == _EDIT_INVOICE_OPERATION_DATE:
        await message.answer(
            'Ktorý dátum chcete upraviť: vystavenia, dodania alebo splatnosti?'
        )
        return

    if operation not in {
        _EDIT_INVOICE_OPERATION_ISSUE_DATE,
        _EDIT_INVOICE_OPERATION_DELIVERY_DATE,
        _EDIT_INVOICE_OPERATION_DUE_DATE,
    }:
        await message.answer(
            'Prosím, napíšte `upraviť číslo faktúry`, `upraviť dátum vystavenia`, '
            '`upraviť dátum dodania` alebo `upraviť dátum splatnosti`.'
        )
        return

    await state.update_data(edit_invoice_date_operation=operation)
    await state.set_state(InvoiceStates.waiting_edit_invoice_date_value)
    await message.answer(_invoice_date_prompt_for_operation(operation))


@router.message(InvoiceStates.waiting_edit_item_action)
async def invoice_edit_item_action(message: Message, state: FSMContext, config: Config) -> None:
    operation = await _resolve_item_edit_action(config=config, user_input_text=(message.text or ''))
    if operation == _EDIT_ITEM_OPERATION_UNKNOWN:
        await message.answer(f'Prosím, {_item_edit_actions_prompt().lower()}')
        return

    state_data = await state.get_data()
    target_item_id = state_data.get('edit_target_item_id')

    if operation == _EDIT_ITEM_OPERATION_REPLACE_SERVICE:
        await state.update_data(edit_item_action_mode='replace_service')
        await state.set_state(InvoiceStates.waiting_edit_service_value)
        await message.answer('Napíšte nový krátky názov služby/položky (napr. `servis`).')
        return

    if operation == _EDIT_ITEM_OPERATION_REPLACE_MAIN_DESCRIPTION:
        await state.update_data(edit_item_action_mode='replace_main_description')
        await state.set_state(InvoiceStates.waiting_edit_description_value)
        await message.answer(
            'Napíšte nový opis položky. Pôvodný opis položky bude nahradený novým textom.'
        )
        return

    if operation == _EDIT_ITEM_OPERATION_ADD_DETAILS:
        await state.update_data(edit_item_action_mode='add_item_details')
        await state.set_state(InvoiceStates.waiting_edit_description_value)
        await message.answer('Napíšte detaily k položke.')
        return

    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        target_index = state_data.get('edit_target_item_index')
        if not isinstance(target_index, int):
            target_index = target_item_id
        if not isinstance(draft, dict) or not isinstance(target_index, int):
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return
        target_item = _draft_item_at_index(draft, target_index)
        if target_item is None:
            await state.clear()
            await message.answer('Položka na úpravu už nie je dostupná. Spustite /invoice znova.')
            return
        if not target_item.get('item_description_raw'):
            await state.set_state(InvoiceStates.waiting_confirm)
            await message.answer('Položka nemá žiadne detaily na vymazanie.')
            return
        target_item['item_description_raw'] = None
        await _show_updated_draft_preview(
            message=message,
            state=state,
            draft=draft,
            success_text='Detaily položky boli vymazané.',
        )
        return

    if not isinstance(target_item_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_service = InvoiceService(config.db_path)
    target_item = next(
        (item for item in invoice_service.get_items_by_invoice_id(invoice_id) if item.id == int(target_item_id)),
        None,
    )
    if target_item is None:
        await state.clear()
        await message.answer('Položka na úpravu už nie je dostupná. Spustite /invoice znova.')
        return
    if target_item.item_description_raw is None:
        await state.set_state(InvoiceStates.waiting_pdf_decision)
        await message.answer('Položka nemá žiadne detaily na vymazanie.')
        return

    invoice_service.update_item_description(item_id=int(target_item_id), item_description_raw=None)
    rebuilt = await _rebuild_pdf_for_existing_invoice(
        message=message,
        state=state,
        config=config,
        invoice_id=int(invoice_id),
    )
    if rebuilt:
        await _send_post_edit_approval_prompt(
            message=message,
            state=state,
            success_text='Detaily položky boli vymazané.',
        )
    return


@router.message(InvoiceStates.waiting_edit_service_value)
async def invoice_edit_service_value(message: Message, state: FSMContext, config: Config) -> None:
    new_service_candidate = (message.text or '').strip()
    if not new_service_candidate:
        await message.answer('Napíšte nový názov služby textom.')
        return

    state_data = await state.get_data()
    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    target_item_id = state_data.get('edit_target_item_id')
    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        target_index = state_data.get('edit_target_item_index') or target_item_id
        if not isinstance(draft, dict) or not isinstance(target_index, int) or message.from_user is None:
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return

        supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
        if supplier is None:
            await state.clear()
            await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
            return

        alias_service = ServiceAliasService(config.db_path)
        resolved_alias, resolved_display_name, allowed_aliases = await _resolve_service_alias_bounded(
            alias_service=alias_service,
            supplier_id=int(supplier.id),
            candidate_text=new_service_candidate,
            config=config,
            context_name='invoice_edit_item_service',
        )
        if not resolved_alias or not resolved_display_name:
            prompt = (
                'Nepodarilo sa jednoznačne určiť službu z povolených aliasov. '
                'Skúste iný názov alebo najprv pridajte alias cez /service.'
            )
            if allowed_aliases:
                prompt += f'\nMožnosti: {", ".join(allowed_aliases[:5])}.'
            await message.answer(prompt)
            return

        target_item = _draft_item_at_index(draft, target_index)
        if target_item is None:
            await state.clear()
            await message.answer('Položka na úpravu už nie je dostupná. Spustite /invoice znova.')
            return
        target_item['service_short_name'] = resolved_alias
        target_item['item_term_canonical_internal'] = resolved_alias
        target_item['service_display_name'] = resolved_display_name
        await _show_updated_draft_preview(
            message=message,
            state=state,
            draft=draft,
            success_text='Služba položky bola zmenená.',
        )
        return

    if not isinstance(invoice_id, int) or not isinstance(target_item_id, int) or message.from_user is None:
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None:
        await state.clear()
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        return

    alias_service = ServiceAliasService(config.db_path)
    resolved_alias, resolved_display_name, allowed_aliases = await _resolve_service_alias_bounded(
        alias_service=alias_service,
        supplier_id=int(supplier.id),
        candidate_text=new_service_candidate,
        config=config,
        context_name='invoice_edit_item_service',
    )
    if not resolved_alias or not resolved_display_name:
        prompt = (
            'Nepodarilo sa jednoznačne určiť službu z povolených aliasov. '
            'Skúste iný názov alebo najprv pridajte alias cez /service.'
        )
        if allowed_aliases:
            prompt += f'\nMožnosti: {", ".join(allowed_aliases[:5])}.'
        await message.answer(prompt)
        return

    invoice_service = InvoiceService(config.db_path)
    invoice_service.update_item_service(
        item_id=int(target_item_id),
        service_short_name=resolved_alias,
        service_display_name=resolved_display_name,
    )

    rebuilt = await _rebuild_pdf_for_existing_invoice(
        message=message,
        state=state,
        config=config,
        invoice_id=int(invoice_id),
    )
    if rebuilt:
        await _send_post_edit_approval_prompt(
            message=message,
            state=state,
            success_text='Služba položky bola zmenená.',
        )


@router.message(InvoiceStates.waiting_edit_invoice_number_value)
async def invoice_edit_invoice_number_value(message: Message, state: FSMContext, config: Config) -> None:
    candidate_number = (message.text or '').strip()
    if not candidate_number:
        await message.answer(
            'Napíšte číslo faktúry vo formáte RRRRNNNN. '
            'Ak hlas nebol jednoznačný, pošlite číslo presne textom.'
        )
        return

    state_data = await state.get_data()
    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        if not isinstance(draft, dict):
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return
        if not _is_valid_invoice_number_for_edit(
            invoice_issue_date=str(draft['issue_date']),
            invoice_number_candidate=candidate_number,
        ):
            await message.answer(
                'Neplatné číslo faktúry. Zadajte číslo vo formáte RRRRNNNN '
                '(pri nejasnom hlase pošlite presný text).'
            )
            return
        if not InvoiceService(config.db_path).is_invoice_number_available(invoice_number=candidate_number):
            await message.answer('Číslo faktúry už existuje. Zadajte prosím iné číslo.')
            return
        draft['invoice_number'] = candidate_number
        draft['invoice_number_manual_override'] = True
        await _show_updated_draft_preview(
            message=message,
            state=state,
            draft=draft,
            success_text='Číslo faktúry bolo upravené.',
        )
        return

    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_service = InvoiceService(config.db_path)
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
        return

    if not _is_valid_invoice_number_for_edit(
        invoice_issue_date=invoice.issue_date,
        invoice_number_candidate=candidate_number,
    ):
        await message.answer(
            'Neplatné číslo faktúry. Zadajte číslo vo formáte RRRRNNNN '
            '(pri nejasnom hlase pošlite presný text).'
        )
        return

    if not invoice_service.is_invoice_number_available(
        invoice_number=candidate_number,
        exclude_invoice_id=invoice_id,
    ):
        await message.answer('Číslo faktúry už existuje. Zadajte prosím iné číslo.')
        return

    previous_pdf_path_value = state_data.get('last_pdf_path')
    previous_pdf_path = Path(previous_pdf_path_value) if isinstance(previous_pdf_path_value, str) and previous_pdf_path_value.strip() else None

    updated = invoice_service.update_invoice_number(
        invoice_id=invoice_id,
        invoice_number=candidate_number,
    )
    if not updated:
        await message.answer('Číslo faktúry už existuje. Zadajte prosím iné číslo.')
        return

    rebuilt = await _rebuild_pdf_for_existing_invoice(
        message=message,
        state=state,
        config=config,
        invoice_id=invoice_id,
    )
    if rebuilt:
        latest_state_data = await state.get_data()
        new_pdf_path_value = latest_state_data.get('last_pdf_path')
        if (
            previous_pdf_path is not None
            and isinstance(new_pdf_path_value, str)
            and previous_pdf_path != Path(new_pdf_path_value)
        ):
            try:
                previous_pdf_path.unlink(missing_ok=True)
            except Exception:
                logger.exception('Failed to cleanup previous invoice PDF after invoice-number edit')
        await _send_post_edit_approval_prompt(
            message=message,
            state=state,
            success_text='Číslo faktúry bolo upravené.',
        )


@router.message(InvoiceStates.waiting_edit_invoice_date_value)
async def invoice_edit_invoice_date_value(message: Message, state: FSMContext, config: Config) -> None:
    candidate_date_raw = (message.text or '').strip()
    if not candidate_date_raw:
        await message.answer(
            'Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.'
        )
        return

    state_data = await state.get_data()
    date_operation = state_data.get('edit_invoice_date_operation')
    if date_operation not in {
        _EDIT_INVOICE_OPERATION_ISSUE_DATE,
        _EDIT_INVOICE_OPERATION_DELIVERY_DATE,
        _EDIT_INVOICE_OPERATION_DUE_DATE,
    }:
        await state.set_state(InvoiceStates.waiting_edit_invoice_action)
        await message.answer(
            'Ktorý dátum chcete upraviť: vystavenia, dodania alebo splatnosti?'
        )
        return

    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        if not isinstance(draft, dict):
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return

        normalized_date_value = await resolve_invoice_date_normalization(
            date_field=str(date_operation),
            user_input_text=candidate_date_raw,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
            invoice_context={
                'invoice_number': draft.get('invoice_number'),
                'issue_date': draft.get('issue_date'),
                'delivery_date': draft.get('delivery_date'),
                'due_date': draft.get('due_date'),
            },
        )
        candidate_date_iso = _parse_strict_issue_date_candidate(normalized_date_value)
        if candidate_date_iso is None:
            await message.answer('Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.')
            return

        candidate_date_obj = date.fromisoformat(candidate_date_iso)
        issue_date_obj = date.fromisoformat(str(draft['issue_date']))
        if date_operation == _EDIT_INVOICE_OPERATION_DUE_DATE and candidate_date_obj < issue_date_obj:
            await message.answer(
                'Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.'
            )
            return
        if date_operation == _EDIT_INVOICE_OPERATION_ISSUE_DATE:
            due_date_obj = date.fromisoformat(str(draft['due_date']))
            if due_date_obj < candidate_date_obj:
                await message.answer(
                    'Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.'
                )
                return

        if date_operation == _EDIT_INVOICE_OPERATION_ISSUE_DATE:
            draft['issue_date'] = candidate_date_iso
            if not bool(draft.get('invoice_number_manual_override')):
                draft['invoice_number'] = InvoiceService(config.db_path).generate_next_invoice_number(
                    candidate_date_obj.year
                )
            success_text = 'Dátum vystavenia bol upravený.'
        elif date_operation == _EDIT_INVOICE_OPERATION_DELIVERY_DATE:
            draft['delivery_date'] = candidate_date_iso
            success_text = 'Dátum dodania bol upravený.'
        else:
            draft['due_date'] = candidate_date_iso
            success_text = 'Dátum splatnosti bol upravený.'

        await _show_updated_draft_preview(
            message=message,
            state=state,
            draft=draft,
            success_text=success_text,
        )
        return

    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_service = InvoiceService(config.db_path)
    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
        return

    normalized_date_value = await resolve_invoice_date_normalization(
        date_field=str(date_operation),
        user_input_text=candidate_date_raw,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        invoice_context={
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date,
            'delivery_date': invoice.delivery_date,
            'due_date': invoice.due_date,
        },
    )
    candidate_date_iso = _parse_strict_issue_date_candidate(normalized_date_value)
    if candidate_date_iso is None:
        await message.answer('Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.')
        return

    candidate_date_obj = date.fromisoformat(candidate_date_iso)
    issue_date_obj = date.fromisoformat(invoice.issue_date)
    if date_operation == _EDIT_INVOICE_OPERATION_DUE_DATE and candidate_date_obj < issue_date_obj:
        await message.answer(
            'Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.'
        )
        return

    if date_operation == _EDIT_INVOICE_OPERATION_ISSUE_DATE:
        due_date_obj = date.fromisoformat(invoice.due_date)
        if due_date_obj < candidate_date_obj:
            await message.answer(
                'Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.'
            )
            return

    previous_pdf_path_value = state_data.get('last_pdf_path')
    previous_pdf_path = (
        Path(previous_pdf_path_value)
        if isinstance(previous_pdf_path_value, str) and previous_pdf_path_value.strip()
        else None
    )

    if date_operation == _EDIT_INVOICE_OPERATION_ISSUE_DATE:
        invoice_service.update_invoice_issue_date(
            invoice_id=invoice_id,
            issue_date=candidate_date_iso,
        )
        success_text = 'Dátum vystavenia bol upravený.'
    elif date_operation == _EDIT_INVOICE_OPERATION_DELIVERY_DATE:
        invoice_service.update_invoice_delivery_date(
            invoice_id=invoice_id,
            delivery_date=candidate_date_iso,
        )
        success_text = 'Dátum dodania bol upravený.'
    else:
        invoice_service.update_invoice_due_date(
            invoice_id=invoice_id,
            due_date=candidate_date_iso,
        )
        success_text = 'Dátum splatnosti bol upravený.'

    rebuilt = await _rebuild_pdf_for_existing_invoice(
        message=message,
        state=state,
        config=config,
        invoice_id=invoice_id,
    )
    if rebuilt:
        latest_state_data = await state.get_data()
        new_pdf_path_value = latest_state_data.get('last_pdf_path')
        if (
            previous_pdf_path is not None
            and isinstance(new_pdf_path_value, str)
            and previous_pdf_path != Path(new_pdf_path_value)
        ):
            try:
                previous_pdf_path.unlink(missing_ok=True)
            except Exception:
                logger.exception('Failed to cleanup previous invoice PDF after invoice-date edit')
        await _send_post_edit_approval_prompt(
            message=message,
            state=state,
            success_text=success_text,
        )


@router.message(InvoiceStates.waiting_edit_description_value)
async def invoice_edit_description_value(message: Message, state: FSMContext, config: Config) -> None:
    new_description_value = (message.text or '').strip()
    state_data = await state.get_data()
    action_mode = state_data.get('edit_item_action_mode')
    if not new_description_value:
        if action_mode == 'replace_main_description':
            await message.answer('Napíšte nový opis položky.')
            return
        await message.answer('Napíšte detaily k položke.')
        return

    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    target_item_id = state_data.get('edit_target_item_id')
    if state_data.get('edit_stage') == 'draft':
        draft = state_data.get('invoice_draft')
        target_index = state_data.get('edit_target_item_index') or target_item_id
        if not isinstance(draft, dict) or not isinstance(target_index, int):
            await state.clear()
            await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
            return
        target_item = _draft_item_at_index(draft, target_index)
        if target_item is None:
            await state.clear()
            await message.answer('Položka na úpravu už nie je dostupná. Spustite /invoice znova.')
            return

        success_text = 'Detaily položky boli doplnené.'
        if action_mode == 'replace_main_description':
            target_item['service_short_name'] = new_description_value
            target_item['item_term_canonical_internal'] = new_description_value
            target_item['service_display_name'] = new_description_value
            success_text = 'Opis položky bol nahradený novým textom.'
        else:
            existing_details = str(target_item.get('item_description_raw') or '').strip()
            details_to_save = (
                f'{existing_details}; {new_description_value}'
                if existing_details
                else new_description_value
            )
            if not validate_item_detail_render_fit(details_to_save, max_lines=2):
                await message.answer(
                    'Text detailov položky je príliš dlhý. '
                    'Skráťte ho prosím tak, aby sa zmestil najviac do 2 riadkov.'
                )
                return
            target_item['item_description_raw'] = details_to_save

        await _show_updated_draft_preview(
            message=message,
            state=state,
            draft=draft,
            success_text=success_text,
        )
        return

    if not isinstance(invoice_id, int) or not isinstance(target_item_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_service = InvoiceService(config.db_path)
    target_item = next(
        (item for item in invoice_service.get_items_by_invoice_id(invoice_id) if item.id == int(target_item_id)),
        None,
    )
    if target_item is None:
        await state.clear()
        await message.answer('Položka na úpravu už nie je dostupná. Spustite /invoice znova.')
        return

    success_text = 'Detaily položky boli doplnené.'
    if action_mode == 'replace_main_description':
        invoice_service.update_item_main_description(
            item_id=int(target_item_id),
            description_raw=new_description_value,
            description_normalized=new_description_value,
        )
        success_text = 'Opis položky bol nahradený novým textom.'
    else:
        existing_details = (target_item.item_description_raw or '').strip()
        details_to_save = (
            f'{existing_details}; {new_description_value}'
            if existing_details
            else new_description_value
        )
        if not validate_item_detail_render_fit(details_to_save, max_lines=2):
            await message.answer(
                'Text detailov položky je príliš dlhý. '
                'Skráťte ho prosím tak, aby sa zmestil najviac do 2 riadkov.'
            )
            return
        invoice_service.update_item_description(
            item_id=int(target_item_id),
            item_description_raw=details_to_save,
        )

    rebuilt = await _rebuild_pdf_for_existing_invoice(
        message=message,
        state=state,
        config=config,
        invoice_id=int(invoice_id),
    )
    if rebuilt:
        await _send_post_edit_approval_prompt(
            message=message,
            state=state,
            success_text=success_text,
        )


@router.message(lambda message: bool((message.text or '').strip()) and not (message.text or '').startswith('/'))
async def semantic_top_level_input(message: Message, state: FSMContext, config: Config) -> None:
    if await state.get_state() is not None:
        return
    await process_invoice_text(
        message=message,
        state=state,
        config=config,
        invoice_text=message.text or '',
    )
