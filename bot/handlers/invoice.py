from __future__ import annotations

from datetime import date, timedelta
import json
import logging
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


class InvoiceStates(StatesGroup):
    waiting_input = State()
    waiting_confirm = State()
    waiting_pdf_decision = State()


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
        f'• Krátky názov služby: {data["service_short_name"]}\n'
        f'• Plný názov služby: {data["service_display_name"]}\n'
        f'• Množstvo: {data["quantity"]} {data["unit"] or ""}\n'
        f'• Suma: {data["amount"]:.2f} {data["currency"]}\n'
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
        'currency': (biznis_sk or {}).get('mena'),
        'delivery_date': (biznis_sk or {}).get('datum_dodania'),
        'due_days': (biznis_sk or {}).get('splatnost_dni'),
        'due_date': (biznis_sk or {}).get('datum_splatnosti'),
    }
    return raw_text, parsed_draft


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

    service_short_name = (parsed_draft.get('item_name_raw') or '').strip()
    amount = _parse_positive_float(parsed_draft.get('amount'))
    quantity = _parse_positive_float(parsed_draft.get('quantity')) or 1.0

    if not service_short_name or amount is None:
        await message.answer('AI návrh je neúplný (chýba položka alebo suma). Doplňte údaje a skúste to znova.')
        await state.clear()
        return

    unit = (parsed_draft.get('unit') or '').strip() or None
    currency = (parsed_draft.get('currency') or 'EUR').strip().upper() or 'EUR'

    issue_date_obj = date.today()
    delivery_date_obj = _parse_date(parsed_draft.get('delivery_date')) or issue_date_obj

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
    service_term_internal = normalize_service_term(service_short_name)
    service_display_name = service_short_name
    if supplier.id is not None:
        resolved = ServiceAliasService(config.db_path).resolve_service_display_name(supplier.id, service_short_name)
        if resolved:
            service_display_name = resolved

    normalized = {
        'raw_text': raw_text,
        'customer_name': contact.name,
        'contact_id': contact.id,
        'service_short_name': service_short_name,
        'item_term_canonical_internal': service_term_internal,
        'service_display_name': service_display_name,
        'quantity': quantity,
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
    answer = (message.text or '').strip().lower()
    if answer not in {'ano', 'nie'}:
        await message.answer('Napíšte ano alebo nie.')
        return

    if answer == 'nie':
        await state.clear()
        await message.answer('Ukladanie faktúry bolo zrušené. Spustite /invoice pre nový pokus.')
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
                item_unit_price=float(draft['amount']) / float(draft['quantity']),
                item_total_price=float(draft['amount']),
            )
        )
    except Exception:
        logger.exception('Invoice save failed')
        await message.answer('Nepodarilo sa uložiť faktúru.')
        await state.clear()
        return

    invoice = invoice_service.get_invoice_by_id(invoice_id)
    if invoice is None:
        await message.answer('Faktúra bola uložená neúplne. Skúste to znova.')
        await state.clear()
        return

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
                    quantity=float(item.quantity),
                    unit=item.unit,
                    unit_price=float(item.unit_price),
                    total_price=float(item.total_price),
                )
                for item in items
            ],
        )
    except Exception:
        logger.exception('PDF generation failed')
        await message.answer('Nepodarilo sa vygenerovať PDF faktúry.')
        await state.clear()
        return

    invoice_service.save_pdf_path(invoice.id, str(pdf_path))

    await message.answer_document(FSInputFile(pdf_path), caption=f'PDF faktúra {invoice.invoice_number} je pripravená na kontrolu.')
    await state.set_state(InvoiceStates.waiting_pdf_decision)
    await state.update_data(last_invoice_number=invoice.invoice_number)
    await message.answer('Ďalší krok: napíšte schváliť alebo upraviť.')


@router.message(InvoiceStates.waiting_pdf_decision)
async def invoice_pdf_decision(message: Message, state: FSMContext) -> None:
    answer = (message.text or '').strip().lower()
    if answer not in {'schváliť', 'upraviť'}:
        await message.answer('Napíšte schváliť alebo upraviť.')
        return

    data = await state.get_data()
    invoice_number = data.get('last_invoice_number', '-')

    if answer == 'schváliť':
        await state.clear()
        await message.answer(f'Faktúra {invoice_number} je označená ako pripravená.')
        return

    await state.clear()
    await message.answer('Úpravy spravíte opätovným spustením /invoice v tejto fáze.')
