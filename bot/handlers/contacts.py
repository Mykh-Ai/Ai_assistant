from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
import re

from bot.config import Config
from bot.services.document_intake import extract_message_document_text
from bot.services.llm_contact_parser import extract_contact_draft
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.semantic_action_resolver import resolve_bounded_confirmation_reply, resolve_semantic_action
from bot.services.supplier_service import SupplierService
from bot.services.validation import validate_dic, validate_email, validate_ic_dph, validate_ico

router = Router(name='contacts')


class ContactStates(StatesGroup):
    name_hint = State()
    source_after_name = State()
    ico = State()
    dic = State()
    ic_dph = State()
    address = State()
    email = State()
    contact_person = State()
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
        f'Email: {data["email"]}\n'
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
        f'Kontaktná osoba: {data.get("contact_person") or "-"}\n\n'
        'Napíšte ano pre uloženie alebo nie pre zrušenie.'
    )


def _missing_prompt(field: str) -> str:
    if field == 'email':
        return 'Nepodarilo sa nájsť e-mailovú adresu. Doplňte ju, prosím.'
    if field == 'address':
        return 'Nepodarilo sa jednoznačne určiť adresu. Spresnite ju, prosím.'
    if field == 'name':
        return 'Nepodarilo sa jednoznačne určiť názov spoločnosti. Spresnite ho, prosím.'
    if field == 'ico':
        return 'Nepodarilo sa nájsť IČO. Doplňte ho, prosím.'
    if field == 'dic':
        return 'Nepodarilo sa nájsť DIČ. Doplňte ho, prosím.'
    return 'Doplňte chýbajúce údaje, prosím.'


def _missing_required_fields(data: dict[str, str]) -> list[str]:
    missing: list[str] = []
    for field in ('name', 'ico', 'dic', 'address', 'email'):
        if not str(data.get(field, '')).strip():
            missing.append(field)
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


async def start_add_contact_intake(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        return

    await state.clear()
    await state.set_state(ContactStates.name_hint)
    await message.answer('V poriadku, vytvoríme nový kontakt. Najprv napíšte názov firmy.')


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
    extraction_source = '\n'.join(part for part in [source_text, document_text or ''] if part.strip())
    resolved_company_hint = company_hint or _extract_company_hint(source_text)
    parsed = await extract_contact_draft(
        source_text=extraction_source,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        company_hint=resolved_company_hint,
    )
    if parsed.get('role_ambiguity') == '1':
        partial_draft = {
            'name': resolved_company_hint or parsed.get('company_name') or '',
            'ico': parsed.get('ico') or '',
            'dic': parsed.get('dic') or '',
            'ic_dph': parsed.get('ic_dph') or '',
            'address': parsed.get('address') or '',
            'email': parsed.get('email') or '',
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
    await message.answer(_contact_draft_summary(draft))


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
        await message.answer(_contact_draft_summary(draft))
        return

    current = missing[0]
    value = user_text.strip()
    if not value:
        await message.answer(_missing_prompt(current))
        return

    if current == 'email' and not validate_email(value):
        await message.answer('Neplatný email. Skúste znova:')
        return
    if current == 'ico' and not validate_ico(value):
        await message.answer('Neplatné ICO. Formát: 8 číslic. Skúste znova:')
        return
    if current == 'dic' and not validate_dic(value):
        await message.answer('Neplatné DIC. Formát: 10 číslic. Skúste znova:')
        return

    draft[current] = value
    missing = missing[1:]
    await state.update_data(contact_intake_draft=draft, contact_missing_fields=missing)
    if missing:
        await message.answer(_missing_prompt(missing[0]))
        return

    await state.set_state(ContactStates.intake_confirm)
    await message.answer(_contact_draft_summary(draft))


async def process_contact_intake_confirm(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    answer_text: str,
) -> None:
    answer = await resolve_bounded_confirmation_reply(
        context_name='contact_confirm',
        expected_reply_type='yes_no_confirmation',
        allowed_outputs=['ano', 'nie', 'unknown'],
        user_input_text=answer_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if answer == 'unknown':
        await message.answer('Napíšte ano alebo nie.')
        return
    if answer == 'nie':
        await state.clear()
        await message.answer('Vytvorenie kontaktu bolo zrušené.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    draft = dict(data.get('contact_intake_draft') or {})
    service = ContactService(config.db_path)
    service.create_or_replace(
        ContactProfile(
            supplier_telegram_id=message.from_user.id,
            name=draft['name'],
            ico=draft['ico'],
            dic=draft['dic'],
            ic_dph=draft.get('ic_dph') or None,
            address=draft['address'],
            email=draft['email'],
            contact_person=draft.get('contact_person') or None,
            source_type='contract_intake',
            source_note='semantic_intake',
            contract_path=draft.get('contract_path') or None,
        )
    )
    await state.clear()
    await message.answer('Kontakt bol uložený.')


@router.message(Command('contact', 'contact_add'))
async def cmd_contact(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier_service = SupplierService(config.db_path)
    if supplier_service.get_by_telegram_id(message.from_user.id) is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier a potom pridajte kontakt.')
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
        await message.answer('Pošlite zmluvu/PDF alebo zadajte IČO.')
        return

    if not validate_ico(value):
        await message.answer('Neplatné ICO. Formát: 8 číslic. Skúste znova:')
        return

    await state.update_data(ico=value)
    await state.set_state(ContactStates.dic)
    await message.answer('3/7 Zadajte DIC (10 číslic):')


@router.message(ContactStates.name_hint)
async def contact_name_hint(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    if message.document is not None:
        await message.answer('V tomto kroku najprv zadajte názov firmy textom.')
        return

    value = (message.text or '').strip()
    if not value:
        await message.answer('Zadajte názov firmy.')
        return

    service = ContactService(config.db_path)
    existing = service.get_by_name(message.from_user.id, value)
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
    await _process_source_after_name_step(message, state, config, bot)


@router.message(ContactStates.ico)
async def contact_ico(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_ico(value):
        await message.answer('Neplatné ICO. Formát: 8 číslic. Skúste znova:')
        return
    await state.update_data(ico=value)
    await state.set_state(ContactStates.dic)
    await message.answer('3/7 Zadajte DIC (10 číslic):')


@router.message(ContactStates.dic)
async def contact_dic(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer('Neplatné DIC. Formát: 10 číslic. Skúste znova:')
        return
    await state.update_data(dic=value)
    await state.set_state(ContactStates.ic_dph)
    await message.answer('4/7 Zadajte IC DPH (voliteľné, pošlite "-"):')


@router.message(ContactStates.ic_dph)
async def contact_ic_dph(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if value == '-':
        await state.update_data(ic_dph='')
    else:
        if not validate_ic_dph(value):
            await message.answer('Neplatné IC DPH. Príklad: SK1234567890. Skúste znova:')
            return
        await state.update_data(ic_dph=value.upper().replace(' ', ''))

    await state.set_state(ContactStates.address)
    await message.answer('5/7 Zadajte adresu:')


@router.message(ContactStates.address)
async def contact_address(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Adresa nemôže byť prázdna. Skúste znova:')
        return
    await state.update_data(address=value)
    await state.set_state(ContactStates.email)
    await message.answer('6/7 Zadajte email:')


@router.message(ContactStates.email)
async def contact_email(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_email(value):
        await message.answer('Neplatný email. Skúste znova:')
        return
    await state.update_data(email=value)
    await state.set_state(ContactStates.contact_person)
    await message.answer('7/7 Zadajte kontaktnú osobu (voliteľné, pošlite "-"):')


@router.message(ContactStates.contact_person)
async def contact_person(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    await state.update_data(contact_person='' if value == '-' else value)

    data = await state.get_data()
    await state.set_state(ContactStates.confirm)
    await message.answer(_summary(data))


@router.message(ContactStates.confirm)
async def contact_confirm(message: Message, state: FSMContext, config: Config) -> None:
    answer = (message.text or '').strip().lower()
    if answer not in {'ano', 'nie'}:
        await message.answer('Napíšte ano alebo nie.')
        return

    if answer == 'nie':
        await state.clear()
        await message.answer('Vytvorenie kontaktu bolo zrušené. Pre nový pokus spustite /contact.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    service = ContactService(config.db_path)
    service.create_or_replace(
        ContactProfile(
            supplier_telegram_id=message.from_user.id,
            name=data['name'],
            ico=data['ico'],
            dic=data['dic'],
            ic_dph=data['ic_dph'] or None,
            address=data['address'],
            email=data['email'],
            contact_person=data['contact_person'] or None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )

    await state.clear()
    await message.answer('Kontakt bol uložený.')


@router.message(ContactStates.intake_missing)
async def contact_intake_missing(message: Message, state: FSMContext) -> None:
    await process_contact_missing_fields(
        message=message,
        state=state,
        user_text=message.text or '',
    )


@router.message(ContactStates.intake_confirm)
async def contact_intake_confirm(message: Message, state: FSMContext, config: Config) -> None:
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
