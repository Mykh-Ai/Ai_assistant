from __future__ import annotations

from datetime import date, timedelta
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from bot.config import Config
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.invoice_service import CreateInvoicePayload, InvoiceService
from bot.services.llm_invoice_parser import parse_invoice_draft
from bot.services.pdf_generator import PdfInvoiceData, PdfInvoiceItem, generate_invoice_pdf
from bot.services.service_alias_service import ServiceAliasService
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


def _resolve_contact_by_name(contact_service: ContactService, telegram_id: int, name: str) -> ContactProfile | None:
    exact = contact_service.get_by_name(telegram_id, name)
    if exact is not None:
        return exact
    return contact_service.get_by_name_case_insensitive(telegram_id, name)


def _format_preview(recognized_text: str | None, data: dict[str, object]) -> str:
    text_part = ''
    if recognized_text:
        text_part = f'<b>Rozpoznaný text:</b>\n{recognized_text}\n\n'

    return (
        f'{text_part}'
        '<b>Náhľad faktúry:</b>\n'
        f'• Odberateľ: {data["customer_name"]}\n'
        f'• Položka (raw): {data["item_name_raw"]}\n'
        f'• Položka (finálna): {data["item_name_final"]}\n'
        f'• Množstvo: {data["quantity"]} {data["unit"] or ""}\n'
        f'• Suma: {data["amount"]:.2f} {data["currency"]}\n'
        f'• Dátum vystavenia: {data["issue_date"]}\n'
        f'• Dátum dodania: {data["delivery_date"]}\n'
        f'• Dátum splatnosti: {data["due_date"]}\n\n'
        'Potvrďte uloženie: napíšte <b>ano</b> alebo <b>nie</b>.'
    )


async def _build_and_store_preview(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    raw_text: str,
    parsed_draft: dict,
) -> None:
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
    contact = _resolve_contact_by_name(contact_service, message.from_user.id, customer_name)
    if contact is None:
        await message.answer(
            'Odberateľ bol rozpoznaný, ale kontakt sa nenašiel v lokálnej databáze. '
            'Pridajte ho cez /contact.'
        )
        await state.clear()
        return

    item_name_raw = (parsed_draft.get('item_name_raw') or '').strip()
    amount = _parse_positive_float(parsed_draft.get('amount'))
    quantity = _parse_positive_float(parsed_draft.get('quantity')) or 1.0

    if not item_name_raw or amount is None:
        await message.answer('Nepodarilo sa pripraviť návrh faktúry. Skontrolujte položku a sumu.')
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
    item_name_final = item_name_raw
    if supplier.id is not None:
        resolved = ServiceAliasService(config.db_path).resolve_alias(supplier.id, item_name_raw)
        if resolved:
            item_name_final = resolved

    normalized = {
        'raw_text': raw_text,
        'customer_name': contact.name,
        'contact_id': contact.id,
        'item_name_raw': item_name_raw,
        'item_name_final': item_name_final,
        'quantity': quantity,
        'unit': unit,
        'amount': amount,
        'currency': currency,
        'issue_date': issue_date_obj.isoformat(),
        'delivery_date': delivery_date_obj.isoformat(),
        'due_days': due_days,
        'due_date': due_date_obj.isoformat(),
    }

    await state.update_data(invoice_draft=normalized)
    await state.set_state(InvoiceStates.waiting_confirm)
    await message.answer(_format_preview(raw_text if raw_text else None, normalized))


async def process_invoice_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    invoice_text: str,
) -> None:
    if not config.openai_api_key:
        await message.answer('Bot nie je nakonfigurovaný: chýba OPENAI_API_KEY.')
        await state.clear()
        return

    try:
        parsed = await parse_invoice_draft(invoice_text, config.openai_api_key, config.openai_llm_model)
    except Exception:
        logger.exception('LLM parsing failed in invoice flow')
        await message.answer('Nepodarilo sa spracovať návrh faktúry.')
        await state.clear()
        return

    await _build_and_store_preview(
        message=message,
        state=state,
        config=config,
        raw_text=invoice_text,
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
                item_description_raw=str(draft['item_name_raw']),
                item_description_normalized=str(draft['item_name_final']),
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
