from __future__ import annotations

from datetime import date, timedelta
import json
import logging
from pathlib import Path
import re
import unicodedata
from uuid import uuid4

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from bot.config import Config
from bot.services.contact_service import ContactLookupResult, ContactService
from bot.services.invoice_service import CreateInvoicePayload, InvoiceService
from bot.services.llm_invoice_parser import LlmInvoicePayloadError, parse_invoice_phase2_payload
from bot.services.pdf_generator import PdfInvoiceData, PdfInvoiceItem, generate_invoice_pdf
from bot.services.service_alias_service import ServiceAliasService
from bot.services.service_term_normalizer import normalize_service_term
from bot.services.supplier_service import SupplierService

router = Router(name='invoice')
logger = logging.getLogger(__name__)


_CREATE_INVOICE_INTENT = 'create_invoice'
_EDIT_INVOICE_INTENT = 'edit_invoice'
_SEND_INVOICE_INTENT = 'send_invoice'
_UNKNOWN_INVOICE_INTENT = 'unknown'
_CONFIRM_PREVIEW = 'confirm_preview'
_CANCEL_PREVIEW = 'cancel_preview'
_APPROVE_PDF_INVOICE = 'approve_pdf_invoice'
_EDIT_PDF_INVOICE = 'edit_pdf_invoice'
_CANCEL_PDF_INVOICE = 'cancel_pdf_invoice'

_CREATE_INVOICE_VERBS_RAW = {
    'vytvor',
    'vytvorit',
    'sprav',
    'urob',
    'створи',
    'створити',
    'зроби',
    'зробити',
    'витвори',
    'витворить',
    'сделай',
    'сделать',
    'создать',
    'создай',
    'выпиши',
    'сформируй',
    'выстави',
}

_RESERVED_EDIT_INVOICE_VERBS_RAW = {
    'upravit',
    'управить',
    'исправь',
    'отредактируй',
}

_RESERVED_SEND_INVOICE_VERBS_RAW = {
    'posli',
    'poslat',
    'відправ',
    'надішли',
    'отправь',
}


class InvoiceStates(StatesGroup):
    waiting_input = State()
    waiting_confirm = State()
    waiting_pdf_decision = State()


def _normalize_intent_token(token: str) -> str:
    lowered = token.strip().lower()
    if not lowered:
        return ''

    normalized = unicodedata.normalize('NFKD', lowered)
    return ''.join(char for char in normalized if not unicodedata.combining(char))


_CREATE_INVOICE_VERBS = {_normalize_intent_token(verb) for verb in _CREATE_INVOICE_VERBS_RAW}
_RESERVED_EDIT_INVOICE_VERBS = {_normalize_intent_token(verb) for verb in _RESERVED_EDIT_INVOICE_VERBS_RAW}
_RESERVED_SEND_INVOICE_VERBS = {_normalize_intent_token(verb) for verb in _RESERVED_SEND_INVOICE_VERBS_RAW}


def _detect_invoice_intent(text: str) -> str:
    tokens = re.findall(r'[^\W\d_]+', text.lower(), flags=re.UNICODE)
    if not tokens:
        return _UNKNOWN_INVOICE_INTENT

    for token in tokens[:3]:
        normalized_token = _normalize_intent_token(token)
        if normalized_token in _RESERVED_EDIT_INVOICE_VERBS:
            return _EDIT_INVOICE_INTENT
        if normalized_token in _RESERVED_SEND_INVOICE_VERBS:
            return _SEND_INVOICE_INTENT
        if normalized_token in _CREATE_INVOICE_VERBS:
            return _CREATE_INVOICE_INTENT

    return _UNKNOWN_INVOICE_INTENT


def _detect_invoice_preview_confirmation(text: str) -> str:
    tokens = re.findall(r'[^\W\d_]+', text.lower(), flags=re.UNICODE)
    if not tokens:
        return _UNKNOWN_INVOICE_INTENT

    confirm_tokens = {
        _normalize_intent_token(token)
        for token in {'áno', 'ano', 'так', 'да', 'ok', 'okej', 'yes'}
    }
    cancel_tokens = {
        _normalize_intent_token(token)
        for token in {'nie', 'ні', 'нет', 'no'}
    }

    for token in tokens[:3]:
        normalized_token = _normalize_intent_token(token)
        if normalized_token in confirm_tokens:
            return _CONFIRM_PREVIEW
        if normalized_token in cancel_tokens:
            return _CANCEL_PREVIEW

    return _UNKNOWN_INVOICE_INTENT


def _detect_invoice_postpdf_decision(text: str) -> str:
    tokens = re.findall(r'[^\W\d_]+', text.lower(), flags=re.UNICODE)
    if not tokens:
        return _UNKNOWN_INVOICE_INTENT

    approve_tokens = {
        _normalize_intent_token(token)
        for token in {
            'schváliť',
            'schvalit',
            'potvrdiť',
            'potvrdit',
            'схвалити',
            'підтвердити',
            'одобрить',
            'подтвердить',
            'áno',
            'ano',
            'так',
            'да',
        }
    }
    edit_tokens = {
        _normalize_intent_token(token)
        for token in {
            'upraviť',
            'upravit',
            'zmeniť',
            'zmenit',
            'управить',
            'редагувати',
            'змінити',
            'исправь',
            'отредактируй',
            'изменить',
        }
    }
    cancel_tokens = {
        _normalize_intent_token(token)
        for token in {
            'zrušiť',
            'zrusit',
            'vymazať',
            'vymazat',
            'zmazať',
            'zmazat',
            'зрушити',
            'скасувати',
            'видалити',
            'удалить',
            'отменить',
            'nie',
            'ні',
            'нет',
        }
    }

    for token in tokens[:3]:
        normalized_token = _normalize_intent_token(token)
        if normalized_token in approve_tokens:
            return _APPROVE_PDF_INVOICE
        if normalized_token in edit_tokens:
            return _EDIT_PDF_INVOICE
        if normalized_token in cancel_tokens:
            return _CANCEL_PDF_INVOICE

    return _UNKNOWN_INVOICE_INTENT


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
        await message.answer('Z vašej správy sa nepodarilo rozpoznať odberateľa.')
        await state.clear()
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
        await message.answer(_contact_lookup_feedback(lookup_result))
        await state.clear()
        return
    contact = lookup_result.matched_contact

    service_short_name_input = (parsed_draft.get('service_term_sk') or parsed_draft.get('item_name_raw') or '').strip()
    service_term_internal = normalize_service_term(service_short_name_input)
    service_short_name = service_term_internal or service_short_name_input

    try:
        quantity, unit_price, amount = _normalize_invoice_amount_semantics(
            raw_text=raw_text,
            quantity_value=parsed_draft.get('quantity'),
            total_value=parsed_draft.get('amount'),
            unit_price_value=parsed_draft.get('unit_price'),
        )
    except ValueError as exc:
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
        await message.answer(f'{exc} Uveďte dátum dodania znova.')
        await state.clear()
        return

    draft_due_days = parsed_draft.get('due_days')
    due_days = supplier.days_due
    if draft_due_days is not None:
        try:
            parsed_due = int(str(draft_due_days))
            if parsed_due > 0:
                due_days = parsed_due
        except ValueError:
            pass

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

    top_level_intent = _detect_invoice_intent(invoice_text)
    if top_level_intent in {_EDIT_INVOICE_INTENT, _SEND_INVOICE_INTENT}:
        await message.answer(
            'Táto akcia s faktúrou zatiaľ nie je podporovaná. '
            'Spustite /invoice pre vytvorenie novej faktúry.'
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
    except LlmInvoicePayloadError:
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


async def process_invoice_preview_confirmation(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    confirmation_text: str,
) -> None:
    answer = _detect_invoice_preview_confirmation(confirmation_text)
    if answer == _UNKNOWN_INVOICE_INTENT:
        await message.answer('Prosím, odpovedzte áno alebo nie.')
        return

    if answer == _CANCEL_PREVIEW:
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
    answer = _detect_invoice_postpdf_decision(decision_text)
    if answer == _UNKNOWN_INVOICE_INTENT:
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

    if answer == _APPROVE_PDF_INVOICE:
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
    if answer == _EDIT_PDF_INVOICE:
        await message.answer(
            'Funkcia úpravy zatiaľ nie je dostupná. Faktúra bola zrušená. '
            'Prosím, vytvorte novú faktúru.'
        )
        return

    await message.answer('Faktúra bola zrušená. Číslo faktúry nebolo finálne potvrdené.')


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


@router.message(InvoiceStates.waiting_pdf_decision)
async def invoice_pdf_decision(message: Message, state: FSMContext, config: Config) -> None:
    await process_invoice_postpdf_decision(
        message=message,
        state=state,
        config=config,
        decision_text=(message.text or ''),
    )
