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
from bot.services.contact_service import ContactLookupResult, ContactService
from bot.services.invoice_service import CreateInvoicePayload, InvoiceService
from bot.services.llm_invoice_parser import LlmInvoicePayloadError, parse_invoice_phase2_payload
from bot.services.pdf_generator import (
    PdfInvoiceData,
    PdfInvoiceItem,
    generate_invoice_pdf,
    validate_item_detail_render_fit,
)
from bot.services.service_alias_service import ServiceAliasService
from bot.services.service_term_normalizer import normalize_service_term
from bot.services.semantic_action_resolver import resolve_bounded_confirmation_reply, resolve_semantic_action
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
    waiting_edit_item_target = State()
    waiting_edit_operation = State()
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
_EDIT_ITEM_OPERATION_REPLACE_SERVICE = 'replace_service'
_EDIT_ITEM_OPERATION_EDIT_DESCRIPTION = 'edit_item_description'
_EDIT_INVOICE_OPERATION_NUMBER = 'edit_invoice_number'
_EDIT_INVOICE_OPERATION_DATE = 'edit_invoice_date'
_EDIT_ITEM_OPERATION_UNKNOWN = 'unknown'
_DESCRIPTION_MODE_SET = 'set'
_DESCRIPTION_MODE_REPLACE = 'replace'
_DESCRIPTION_MODE_CLEAR = 'clear'
_INVOICE_NUMBER_PATTERN = re.compile(r'^(?:19|20)\d{6}$')

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


def _service_alias_bridge_forms(service_term_internal: str | None) -> tuple[str, ...]:
    if not service_term_internal:
        return ()

    deterministic_bridge_forms = {
        'oprava': ('opravy',),
    }
    return deterministic_bridge_forms.get(service_term_internal, ())


def _resolve_service_display_name(
    *,
    alias_service: ServiceAliasService,
    supplier_id: int,
    service_short_name: str,
    service_term_internal: str | None,
) -> str:
    lookup_candidates: list[str] = [service_short_name]
    if service_term_internal:
        lookup_candidates.append(service_term_internal)
        lookup_candidates.extend(_service_alias_bridge_forms(service_term_internal))

    seen: set[str] = set()
    for candidate in lookup_candidates:
        normalized_candidate = candidate.strip().lower()
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        resolved = alias_service.resolve_service_display_name(supplier_id, candidate)
        if resolved:
            return resolved

    return service_short_name


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

    return (
        f'{text_part}'
        '<b>Náhľad faktúry:</b>\n'
        f'• Odberateľ: {data["customer_name"]}\n'
        f'• Plný názov služby: {data["service_display_name"]}\n'
        f'• Množstvo: {data["quantity"]} {data["unit"] or ""}\n'
        f'• Cena za m.j.: {data["unit_price"]:.2f} {data["currency"]}\n'
        f'• Suma spolu: {data["amount"]:.2f} {data["currency"]}\n'
        f'• Dátum vystavenia: {data["issue_date"]}\n'
        f'• Dátum dodania: {data["delivery_date"]}\n'
        f'• Dátum splatnosti: {data["due_date"]}\n\n'
        'Potvrďte uloženie: napíšte <b>ano</b> alebo <b>nie</b>.'
    )


def _detect_edit_operation(value: str) -> str:
    normalized = ' '.join((value or '').casefold().split())
    if not normalized:
        return _EDIT_ITEM_OPERATION_UNKNOWN
    if (
        ('dátum' in normalized or 'datum' in normalized or 'date' in normalized)
        and ('faktúr' in normalized or 'faktur' in normalized or 'invoice' in normalized)
    ):
        return _EDIT_INVOICE_OPERATION_DATE
    if (
        ('faktúr' in normalized or 'faktur' in normalized or 'invoice' in normalized)
        and ('čísl' in normalized or 'cisl' in normalized or 'number' in normalized or 'num' in normalized)
    ):
        return _EDIT_INVOICE_OPERATION_NUMBER
    if any(token in normalized for token in ('služb', 'sluzb', 'service', 'položk', 'polozk')):
        return _EDIT_ITEM_OPERATION_REPLACE_SERVICE
    if any(token in normalized for token in ('opis', 'popis', 'detail', 'poznám', 'poznam', 'description')):
        return _EDIT_ITEM_OPERATION_EDIT_DESCRIPTION
    return _EDIT_ITEM_OPERATION_UNKNOWN


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


def _detect_description_mode(value: str) -> str:
    normalized = ' '.join((value or '').casefold().split())
    if any(token in normalized for token in ('vymaž', 'vymaz', 'zmaž', 'zmaz', 'clear', 'remove', 'odstráň', 'odstran')):
        return _DESCRIPTION_MODE_CLEAR
    if any(token in normalized for token in ('nahraď', 'nahrad', 'zmeň', 'zmen', 'uprav', 'replace')):
        return _DESCRIPTION_MODE_REPLACE
    return _DESCRIPTION_MODE_SET


def _extract_invoice_draft_from_phase2_payload(payload: dict) -> tuple[str, dict[str, object]]:
    vstup = payload.get('vstup') if isinstance(payload, dict) else {}
    biznis_sk = payload.get('biznis_sk') if isinstance(payload, dict) else {}

    raw_text = str((vstup or {}).get('povodny_text') or '').strip()
    parsed_draft = {
        'customer_name': (biznis_sk or {}).get('odberatel_kandidat'),
        'item_name_raw': (biznis_sk or {}).get('polozka_povodna'),
        'service_term_sk': (biznis_sk or {}).get('termin_sluzby_sk'),
        'quantity': (biznis_sk or {}).get('mnozstvo'),
        'unit': (biznis_sk or {}).get('jednotka'),
        'amount': (biznis_sk or {}).get('suma'),
        'unit_price': (biznis_sk or {}).get('cena_za_jednotku'),
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
    if lookup_result.state not in {'exact_match', 'normalized_match'} or lookup_result.matched_contact is None:
        await _start_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            request_id=request_id,
            raw_text=raw_text,
            parsed_draft=parsed_draft,
            unresolved_slot=_SLOT_CUSTOMER,
            bounded_choices=[candidate.name for candidate in lookup_result.candidates[:3]],
            debug_payload={
                'lookup_feedback': _contact_lookup_feedback(lookup_result),
                'lookup_state': lookup_result.state,
            },
            prefer_service_state=False,
            update_hint='Prosím, spresnite názov odberateľa a skúste to znova.',
        )
        return
    contact = lookup_result.matched_contact

    service_short_name_input = (parsed_draft.get('service_term_sk') or parsed_draft.get('item_name_raw') or '').strip()
    service_term_internal = normalize_service_term(service_short_name_input)
    service_short_name = service_term_internal or service_short_name_input

    quantity_value = parsed_draft.get('quantity')
    quantity_raw = _parse_positive_float(quantity_value)
    if quantity_value is not None and quantity_raw is None:
        await _start_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            request_id=request_id,
            raw_text=raw_text,
            parsed_draft=parsed_draft,
            unresolved_slot=_SLOT_QUANTITY,
        )
        return

    total_raw = _parse_positive_float(parsed_draft.get('amount'))
    unit_price_raw = _parse_positive_float(parsed_draft.get('unit_price'))
    has_multiplier_hint = bool(_MULTIPLIER_HINT_PATTERN.search(raw_text))
    explicit_amount_pattern = _parse_confident_unit_price_pattern(raw_text)
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
            unresolved_slot=_SLOT_QUANTITY_UNIT_PRICE,
        )
        return

    try:
        quantity, unit_price, amount = _normalize_invoice_amount_semantics(
            raw_text=raw_text,
            quantity_value=quantity_value,
            total_value=parsed_draft.get('amount'),
            unit_price_value=parsed_draft.get('unit_price'),
        )
    except ValueError as exc:
        if 'chýba suma' in str(exc):
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=request_id,
                raw_text=raw_text,
                parsed_draft=parsed_draft,
                unresolved_slot=_SLOT_QUANTITY_UNIT_PRICE,
            )
            return
        await message.answer(f'{exc} Skúste formuláciu typu "2x po 1500 EUR".')
        await state.clear()
        return

    if not service_short_name:
        await message.answer('AI návrh je neúplný (chýba položka alebo suma). Doplňte údaje a skúste to znova.')
        await state.clear()
        return

    unit = (parsed_draft.get('unit') or '').strip() or None
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
    service_display_name = service_short_name
    if supplier.id is not None:
        service_display_name = _resolve_service_display_name(
            alias_service=ServiceAliasService(config.db_path),
            supplier_id=supplier.id,
            service_short_name=service_short_name,
            service_term_internal=service_term_internal,
        )

    normalized = {
        'raw_text': raw_text,
        'customer_name': contact.name,
        'contact_id': contact.id,
        'service_short_name': service_short_name,
        'item_term_canonical_internal': service_term_internal,
        'service_display_name': service_display_name,
        'quantity': quantity,
        'unit_price': unit_price,
        'unit': unit,
        'amount': amount,
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
            'service_short_name': service_short_name,
            'service_display_name': service_display_name,
            'service_term_canonical_internal': service_term_internal,
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
        canonical_service_term = normalize_service_term(normalized_text)
        if canonical_service_term is None:
            return False
        parsed_draft['service_term_sk'] = canonical_service_term
        parsed_draft['item_name_raw'] = canonical_service_term
        return True
    if unresolved_slot == _SLOT_CUSTOMER:
        if not normalized_text:
            return False
        parsed_draft['customer_name'] = normalized_text
        return True
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
        if exc.error_code in {'service_term_unresolved', 'customer_unresolved'} and isinstance(exc.partial_payload, dict):
            raw_text, parsed = _extract_invoice_draft_from_phase2_payload(exc.partial_payload)
            await _start_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                request_id=flow_request_id,
                raw_text=raw_text or invoice_text,
                parsed_draft=parsed,
                unresolved_slot=_SLOT_SERVICE if exc.error_code == 'service_term_unresolved' else _SLOT_CUSTOMER,
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


async def process_invoice_preview_confirmation(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    confirmation_text: str,
) -> None:
    answer = await resolve_bounded_confirmation_reply(
        context_name='invoice_preview_confirmation',
        expected_reply_type='yes_no_confirmation',
        allowed_outputs=['ano', 'nie', 'unknown'],
        user_input_text=confirmation_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if answer == 'unknown':
        await message.answer('Prosím, odpovedzte áno alebo nie.')
        return

    if answer == 'nie':
        await state.clear()
        await message.answer('Vytvorenie faktúry bolo zrušené.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        await state.clear()
        return

    state_data = await state.get_data()
    draft = state_data.get('invoice_draft')
    if not draft:
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
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

    contact = ContactService(config.db_path).get_by_name_case_insensitive(message.from_user.id, str(draft['customer_name']))
    if contact is None:
        await message.answer('Kontakt odberateľa sa nenašiel v databáze. Pridajte ho cez /contact.')
        await state.clear()
        return

    invoice_service = InvoiceService(config.db_path)
    invoice_id: int | None = None
    pdf_path = None

    try:
        invoice_id = invoice_service.create_invoice_with_one_item(
            CreateInvoicePayload(
                supplier_telegram_id=message.from_user.id,
                contact_id=int(contact_id),
                issue_date=str(draft['issue_date']),
                delivery_date=str(draft['delivery_date']),
                due_date=str(draft['due_date']),
                due_days=int(draft['due_days']),
                total_amount=float(draft['amount']),
                currency=str(draft['currency']),
                status='draft_pdf_ready',
                item_description_raw=str(draft['service_short_name']),
                item_description_normalized=str(draft['service_display_name']),
                item_quantity=float(draft['quantity']),
                item_unit=str(draft['unit']) if draft['unit'] else None,
                item_unit_price=float(draft['unit_price']),
                item_total_price=float(draft['amount']),
            )
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
            caption=f'PDF faktúra {invoice.invoice_number} je pripravená na kontrolu.',
        )
        await state.set_state(InvoiceStates.waiting_pdf_decision)
        await state.update_data(
            last_invoice_id=invoice.id,
            last_invoice_number=invoice.invoice_number,
            last_pdf_path=str(pdf_path),
        )
        await message.answer('Ďalší krok: napíšte schváliť, upraviť alebo zrušiť.')
    except Exception:
        logger.exception('Invoice save/pdf send failed')
        db_cleanup_failed = False
        if invoice_id is not None:
            try:
                invoice_service.delete_invoice_with_items(invoice_id)
            except Exception:
                logger.exception('Cleanup after failed PDF generation failed')
                db_cleanup_failed = True
        if pdf_path is not None:
            try:
                pdf_path.unlink(missing_ok=True)
            except Exception:
                logger.exception('PDF cleanup after failed generation/sending failed')
        if db_cleanup_failed:
            await state.clear()
            await message.answer('Nepodarilo sa dokončiť zrušenie neúplnej faktúry. Spustite /invoice znova.')
            return
        await state.clear()
        await message.answer('Nepodarilo sa dokončiť vytvorenie PDF faktúry. Skúste to znova.')


async def process_invoice_postpdf_decision(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    answer = await resolve_bounded_confirmation_reply(
        context_name='invoice_postpdf_decision',
        expected_reply_type='postpdf_decision',
        allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if answer == 'unknown':
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
        await _start_invoice_item_edit_flow(
            message=message,
            state=state,
            config=config,
            invoice_id=invoice_id,
        )
        return

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


async def _start_invoice_item_edit_flow(
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

    await state.update_data(edit_invoice_id=invoice_id)
    if len(items) == 1:
        await state.update_data(edit_target_item_index=1, edit_target_item_id=items[0].id)
        await state.set_state(InvoiceStates.waiting_edit_operation)
        await message.answer(
            _format_item_edit_preview(invoice.invoice_number, items[0], 1)
            + '\n\nVyberte úpravu: napíšte `upraviť číslo faktúry`, `upraviť dátum faktúry`, `zmeniť službu` alebo `upraviť opis položky`.',
        )
        return

    await state.set_state(InvoiceStates.waiting_edit_item_target)
    await message.answer(
        f'Faktúra {invoice.invoice_number} má viac položiek. '
        'Napíšte číslo položky, ktorú chcete upraviť (napr. 1, 2, 3), '
        'alebo napíšte `upraviť číslo faktúry` alebo `upraviť dátum faktúry`.'
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
    operation = _detect_edit_operation(raw_value)
    if operation in {_EDIT_INVOICE_OPERATION_NUMBER, _EDIT_INVOICE_OPERATION_DATE}:
        state_data = await state.get_data()
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
                'Napíšte nové číslo faktúry textom vo formáte RRRRNNNN.'
            )
            return

        await state.set_state(InvoiceStates.waiting_edit_invoice_date_value)
        await message.answer(
            f'Aktuálny dátum faktúry je {invoice.issue_date}. '
            'Napíšte nový dátum textom vo formáte DD.MM.RRRR.'
        )
        return

    if not raw_value.isdigit():
        await message.answer(
            'Prosím, zadajte číslo položky, ktorú chcete upraviť (napr. 1), '
            'alebo napíšte `upraviť číslo faktúry` alebo `upraviť dátum faktúry`.'
        )
        return
    target_index = int(raw_value)

    state_data = await state.get_data()
    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    invoice_service = InvoiceService(config.db_path)
    items = invoice_service.get_items_by_invoice_id(invoice_id)
    target_item = _resolve_target_item_from_index(invoice_items=items, target_item_index=target_index)
    if target_item is None:
        await message.answer('Taká položka neexistuje. Zadajte prosím platné číslo položky.')
        return

    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await state.clear()
        await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
        return

    await state.update_data(edit_target_item_index=target_index, edit_target_item_id=target_item.id)
    await state.set_state(InvoiceStates.waiting_edit_operation)
    await message.answer(
        _format_item_edit_preview(invoice.invoice_number, target_item, target_index)
        + '\n\nVyberte úpravu: napíšte `upraviť číslo faktúry`, `upraviť dátum faktúry`, `zmeniť službu` alebo `upraviť opis položky`.',
    )


@router.message(InvoiceStates.waiting_edit_operation)
async def invoice_edit_operation(message: Message, state: FSMContext, config: Config) -> None:
    operation = _detect_edit_operation(message.text or '')
    if operation == _EDIT_ITEM_OPERATION_UNKNOWN:
        await message.answer(
            'Prosím, napíšte `upraviť číslo faktúry`, `upraviť dátum faktúry`, `zmeniť službu` alebo `upraviť opis položky`.'
        )
        return

    state_data = await state.get_data()
    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    target_item_id = state_data.get('edit_target_item_id')
    if not isinstance(invoice_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    if operation == _EDIT_INVOICE_OPERATION_NUMBER:
        invoice = InvoiceService(config.db_path).get_invoice_by_id(invoice_id)
        if invoice is None:
            await state.clear()
            await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
            return
        await state.set_state(InvoiceStates.waiting_edit_invoice_number_value)
        await message.answer(
            f'Aktuálne číslo faktúry je {invoice.invoice_number}. '
            'Napíšte nové číslo faktúry textom vo formáte RRRRNNNN.'
        )
        return
    if operation == _EDIT_INVOICE_OPERATION_DATE:
        invoice = InvoiceService(config.db_path).get_invoice_by_id(invoice_id)
        if invoice is None:
            await state.clear()
            await message.answer('Faktúra už nie je dostupná. Spustite /invoice znova.')
            return
        await state.set_state(InvoiceStates.waiting_edit_invoice_date_value)
        await message.answer(
            f'Aktuálny dátum faktúry je {invoice.issue_date}. '
            'Napíšte nový dátum textom vo formáte DD.MM.RRRR.'
        )
        return

    if not isinstance(target_item_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    if operation == _EDIT_ITEM_OPERATION_REPLACE_SERVICE:
        await state.set_state(InvoiceStates.waiting_edit_service_value)
        await message.answer('Napíšte nový krátky názov služby/položky textom (napr. `servis`).')
        return

    await state.set_state(InvoiceStates.waiting_edit_description_value)
    await message.answer(
        'Napíšte nový opis položky textom. '
        'Ak chcete opis vymazať, napíšte `vymaž opis`.'
    )


@router.message(InvoiceStates.waiting_edit_service_value)
async def invoice_edit_service_value(message: Message, state: FSMContext, config: Config) -> None:
    new_service_candidate = (message.text or '').strip()
    if not new_service_candidate:
        await message.answer('Napíšte nový názov služby textom.')
        return

    state_data = await state.get_data()
    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    target_item_id = state_data.get('edit_target_item_id')
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
    service_term_internal = normalize_service_term(new_service_candidate)
    resolved_display_name = alias_service.resolve_service_display_name(int(supplier.id), new_service_candidate)
    if not resolved_display_name and service_term_internal:
        resolved_display_name = alias_service.resolve_service_display_name(int(supplier.id), service_term_internal)
    if not resolved_display_name and service_term_internal:
        for bridge_candidate in _service_alias_bridge_forms(service_term_internal):
            resolved_display_name = alias_service.resolve_service_display_name(int(supplier.id), bridge_candidate)
            if resolved_display_name:
                break
    if not resolved_display_name:
        await message.answer(
            'Nepodarilo sa jednoznačne určiť službu zo slovníka aliasov. '
            'Skúste iný názov alebo najprv pridajte alias cez /service.'
        )
        return

    invoice_service = InvoiceService(config.db_path)
    invoice_service.update_item_service(
        item_id=int(target_item_id),
        service_short_name=new_service_candidate,
        service_display_name=resolved_display_name,
    )

    rebuilt = await _rebuild_pdf_for_existing_invoice(
        message=message,
        state=state,
        config=config,
        invoice_id=int(invoice_id),
    )
    if rebuilt:
        await message.answer('Služba položky bola upravená. Napíšte: schváliť, upraviť alebo zrušiť.')


@router.message(InvoiceStates.waiting_edit_invoice_number_value)
async def invoice_edit_invoice_number_value(message: Message, state: FSMContext, config: Config) -> None:
    candidate_number = (message.text or '').strip()
    if not candidate_number:
        await message.answer('Napíšte číslo faktúry textom vo formáte RRRRNNNN.')
        return

    state_data = await state.get_data()
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

    if not _is_valid_invoice_number_for_edit(
        invoice_issue_date=invoice.issue_date,
        invoice_number_candidate=candidate_number,
    ):
        await message.answer('Neplatné číslo faktúry. Zadajte prosím číslo vo formáte RRRRNNNN.')
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
        await message.answer('Číslo faktúry bolo upravené. Napíšte: schváliť, upraviť alebo zrušiť.')


@router.message(InvoiceStates.waiting_edit_invoice_date_value)
async def invoice_edit_invoice_date_value(message: Message, state: FSMContext, config: Config) -> None:
    candidate_date_raw = (message.text or '').strip()
    if not candidate_date_raw:
        await message.answer('Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.')
        return

    candidate_issue_date_iso = _parse_strict_issue_date_candidate(candidate_date_raw)
    if candidate_issue_date_iso is None:
        await message.answer('Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.')
        return

    state_data = await state.get_data()
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

    previous_pdf_path_value = state_data.get('last_pdf_path')
    previous_pdf_path = (
        Path(previous_pdf_path_value)
        if isinstance(previous_pdf_path_value, str) and previous_pdf_path_value.strip()
        else None
    )

    invoice_service.update_invoice_issue_date(
        invoice_id=invoice_id,
        issue_date=candidate_issue_date_iso,
    )
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
        await message.answer('Dátum faktúry bol upravený. Napíšte: schváliť, upraviť alebo zrušiť.')


@router.message(InvoiceStates.waiting_edit_description_value)
async def invoice_edit_description_value(message: Message, state: FSMContext, config: Config) -> None:
    new_description_value = (message.text or '').strip()
    if not new_description_value:
        await message.answer('Napíšte opis položky textom alebo `vymaž opis`.')
        return

    state_data = await state.get_data()
    invoice_id = state_data.get('edit_invoice_id') or state_data.get('last_invoice_id')
    target_item_id = state_data.get('edit_target_item_id')
    if not isinstance(invoice_id, int) or not isinstance(target_item_id, int):
        await state.clear()
        await message.answer('Návrh faktúry už nie je dostupný. Spustite /invoice znova.')
        return

    description_mode = _detect_description_mode(new_description_value)
    description_to_save: str | None = new_description_value
    if description_mode == _DESCRIPTION_MODE_CLEAR:
        description_to_save = None
    elif not validate_item_detail_render_fit(new_description_value, max_lines=2):
        await message.answer(
            'Text do opisu položky je príliš dlhý. '
            'Skráťte ho prosím tak, aby sa zmestil najviac do 2 riadkov.'
        )
        return

    invoice_service = InvoiceService(config.db_path)
    invoice_service.update_item_description(
        item_id=int(target_item_id),
        item_description_raw=description_to_save,
    )

    rebuilt = await _rebuild_pdf_for_existing_invoice(
        message=message,
        state=state,
        config=config,
        invoice_id=int(invoice_id),
    )
    if rebuilt:
        await message.answer('Opis položky bol upravený. Napíšte: schváliť, upraviť alebo zrušiť.')


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
