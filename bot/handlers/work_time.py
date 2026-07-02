from __future__ import annotations

from datetime import datetime, time

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile, Message

from bot.config import Config
from bot.keyboards.decision import (
    answer_with_decision_keyboard,
    approve_edit_cancel_keyboard,
    delete_cancel_keyboard,
    yes_no_keyboard,
    work_time_missing_days_keyboard,
    work_time_open_conflict_keyboard,
)
from bot.services.decision_resolver import (
    resolve_approve_edit_cancel,
    resolve_yes_no,
    resolve_work_time_missing_days_choice,
    resolve_work_time_open_conflict_choice,
)
from bot.services.work_time import (
    WorkTimeCandidate,
    WorkTimeDay,
    WorkTimeService,
    format_candidate_preview,
    format_day_summary,
    format_month_summary,
    is_lunch_break_disable_request,
    parse_close_candidate,
    parse_duration_entry_candidate,
    parse_explicit_month,
    parse_lunch_break_minutes,
    parse_manual_range_candidate,
    parse_report_month,
    resolve_work_time_entry_candidate,
)


router = Router(name='work_time')


class WorkTimeStates(StatesGroup):
    waiting_manual_range_confirm = State()
    waiting_manual_range_input = State()
    waiting_close_preview_confirm = State()
    waiting_close_input = State()
    waiting_delete_month_input = State()
    waiting_delete_month_confirm = State()
    waiting_lunch_break_initial_choice = State()
    waiting_lunch_break_value = State()
    waiting_lunch_break_update_value = State()
    waiting_lunch_break_update_confirm = State()
    waiting_open_day_conflict_choice = State()
    waiting_missing_days_choice = State()


@router.message(Command('dochadzka'))
async def cmd_dochadzka(message: Message, state: FSMContext, config: Config) -> None:
    await state.clear()
    await message.answer(
        'Evidencia pracovneho casu je ciastocny OfficeFlow modul.\n\n'
        'Mozete napisat napriklad:\n'
        '- zacinam pracovny den\n'
        '- zatvor den o 17:00\n'
        '- zatvor den 10 hodin\n'
        '- pracoval som dnes od 5:30 do 17:00\n'
        '- vytvor vykaz hodin za jun 2026\n'
        '- nastav obednu prestavku na 30 minut\n'
        '- vymaz dochadzku za jul 2026\n\n'
        'Vykaz pocita ciste hodiny po nastavenej obednej prestavke. '
        'Nie je to mzdova dochadzka, vypocet mzdy ani pravny HR doklad.'
    )


async def start_open_work_day(message: Message, state: FSMContext, config: Config) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    result = WorkTimeService(config.db_path).open_day(
        telegram_id=telegram_id,
        source_message_id=getattr(message, 'message_id', None),
    )
    if result.ok and result.reason == 'already_open' and result.day is not None:
        await state.clear()
        await message.answer(f'Pracovny den je uz otvoreny: {format_day_summary(result.day)}')
        return
    if result.ok and result.day is not None:
        await state.clear()
        await message.answer(f'Pracovny den je otvoreny.\n{format_day_summary(result.day)}')
        return
    if result.reason == 'previous_open_day' and result.conflict_day is not None:
        await state.update_data(work_time_conflict_day_id=result.conflict_day.id)
        await state.set_state(WorkTimeStates.waiting_open_day_conflict_choice)
        await answer_with_decision_keyboard(
            message,
            'Predchadzajuci pracovny den je stale otvoreny:\n'
            f'{format_day_summary(result.conflict_day)}\n\n'
            'Najprv ho uzavrite, doplnte cas, preskocte alebo zruste tento krok.',
            work_time_open_conflict_keyboard(),
        )
        return
    await state.clear()
    await message.answer('Dnesny pracovny den uz ma zaznam. Uprava existujuceho dna je mimo tohto MVP.')


async def start_close_work_day(message: Message, state: FSMContext, config: Config, *, text: str) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    service = WorkTimeService(config.db_path)
    open_day = service.get_open_day(telegram_id=telegram_id)
    if open_day is None:
        manual_candidate = await _resolve_manual_entry_candidate(text, config)
        if manual_candidate is not None:
            await _preview_manual_candidate(message, state, manual_candidate)
            return
        await state.clear()
        await message.answer('Nemate otvoreny pracovny den. Ak chcete doplnit den spatne, napiste napriklad: pracoval som dnes od 5:30 do 17:00 alebo dnes 10 hodin.')
        return

    candidate = parse_close_candidate(text, open_day=open_day)
    if candidate is not None and candidate.close_mode == 'close_now' and _should_try_llm_work_time_slots(text):
        llm_candidate = await resolve_work_time_entry_candidate(
            user_input_text=text,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
            open_day=open_day,
        )
        if llm_candidate is not None:
            candidate = llm_candidate
    if candidate is None or candidate.close_mode == 'close_now':
        result = service.close_open_day(
            telegram_id=telegram_id,
            source_message_id=getattr(message, 'message_id', None),
        )
        await state.clear()
        await _answer_work_time_result(message, result, success_prefix='Pracovny den je uzavrety.')
        return

    await state.update_data(
        work_time_close_candidate=_candidate_to_state(candidate),
        work_time_close_open_day_id=open_day.id,
    )
    await state.set_state(WorkTimeStates.waiting_close_preview_confirm)
    await answer_with_decision_keyboard(
        message,
        'Skontrolujte uzavretie pracovneho dna:\n'
        f'{format_candidate_preview(candidate, open_day=open_day, lunch_break_minutes=_effective_lunch_break_minutes_for_user(config, telegram_id))}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


async def start_add_work_time_entry(message: Message, state: FSMContext, config: Config, *, text: str) -> None:
    candidate = await _resolve_manual_entry_candidate(text, config)
    if candidate is None:
        await state.set_state(WorkTimeStates.waiting_manual_range_input)
        await message.answer('Napiste rozsah alebo pocet hodin, napriklad: pracoval som dnes od 5:30 do 17:00 alebo dnes 10 hodin.')
        return
    await _preview_manual_candidate(message, state, candidate)


async def start_generate_work_time_report(
    message: Message,
    state: FSMContext,
    config: Config,
    *,
    text: str,
    source_channel: str = 'text',
) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    year, month = parse_report_month(text)
    service = WorkTimeService(config.db_path)
    settings = service.get_lunch_break_settings(telegram_id=telegram_id)
    if not settings.configured:
        await state.update_data(
            work_time_pending_report_year=year,
            work_time_pending_report_month=month,
            work_time_pending_report_source_channel=source_channel,
        )
        await state.set_state(WorkTimeStates.waiting_lunch_break_initial_choice)
        await answer_with_decision_keyboard(
            message,
            'Chcete odpočítavať obednú prestávku?',
            yes_no_keyboard(yes_label='Áno', no_label='Nie'),
        )
        return
    await _send_work_time_report(message, state, config, telegram_id=telegram_id, year=year, month=month)


async def start_update_work_time_lunch_break(message: Message, state: FSMContext, config: Config, *, text: str) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    if is_lunch_break_disable_request(text):
        await _preview_lunch_break_update(message, state, enabled=False, minutes=0)
        return
    minutes = parse_lunch_break_minutes(text)
    if minutes is None:
        await state.set_state(WorkTimeStates.waiting_lunch_break_update_value)
        await message.answer('Ak chcete zmenit trvanie obednej prestavky, napiste alebo povedzte pocet minut.')
        return
    await _preview_lunch_break_update(message, state, enabled=minutes > 0, minutes=minutes)


async def start_delete_work_time_month(message: Message, state: FSMContext, config: Config, *, text: str) -> None:
    selected = parse_explicit_month(text)
    if selected is None:
        await state.set_state(WorkTimeStates.waiting_delete_month_input)
        await message.answer('Za ktory mesiac chcete vymazat dochadzku? Napiste napriklad: jul 2026 alebo 2026-07.')
        return
    await _preview_delete_month(message, state, config, year=selected[0], month=selected[1])


@router.message(WorkTimeStates.waiting_delete_month_input)
async def work_time_delete_month_input(message: Message, state: FSMContext, config: Config) -> None:
    selected = parse_explicit_month(message.text or '')
    if selected is None:
        await message.answer('Mesiac sa nepodarilo rozpoznat. Napiste napriklad: jul 2026 alebo 2026-07, pripadne zrusit.')
        return
    await _preview_delete_month(message, state, config, year=selected[0], month=selected[1])


@router.message(WorkTimeStates.waiting_delete_month_confirm)
async def work_time_delete_month_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_yes_no(
        context_name='work_time_delete_month_confirm',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'no':
        await state.clear()
        await message.answer('Vymazanie dochadzky som zrusil. Nic sa nezmenilo.')
        return
    if decision != 'yes':
        await answer_with_decision_keyboard(
            message,
            'Vymazat tieto ulozene zaznamy dochadzky alebo zrusit?',
            delete_cancel_keyboard(delete_label='Vymazat dochadzku', cancel_label='Zrusit'),
        )
        return

    telegram_id = _telegram_id(message)
    data = await state.get_data()
    try:
        year = int(data['work_time_delete_month_year'])
        month = int(data['work_time_delete_month_month'])
    except (KeyError, TypeError, ValueError):
        await state.clear()
        await message.answer('Nahlad vymazania uz nie je dostupny. Skuste poziadavku zadat znova.')
        return
    if telegram_id is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return

    summary = WorkTimeService(config.db_path).delete_month(
        telegram_id=telegram_id,
        year=year,
        month=month,
        source_message_id=getattr(message, 'message_id', None),
    )
    await state.clear()
    if summary.row_count == 0:
        await message.answer('Za vybrany mesiac uz nie je co vymazat.')
        return
    await message.answer(
        'Vymazal som ulozene zaznamy dochadzky pre vybrany mesiac.\n'
        f'{format_month_summary(summary)}\n\n'
        'Mesacne Excel vykazy vytvorene na poziadanie nie su kanonicke data; tento krok maze DB zaznamy dochadzky.'
    )


@router.message(WorkTimeStates.waiting_lunch_break_initial_choice)
async def work_time_lunch_break_initial_choice(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_yes_no(
        context_name='work_time_lunch_break_initial_choice',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    if decision == 'no':
        WorkTimeService(config.db_path).save_lunch_break_settings(telegram_id=telegram_id, enabled=False, minutes=0)
        await _continue_pending_work_time_report(message, state, config, telegram_id=telegram_id)
        return
    if decision == 'yes':
        await state.set_state(WorkTimeStates.waiting_lunch_break_value)
        await message.answer('Napíšte alebo povedzte trvanie obednej prestávky v minútach.')
        return
    await answer_with_decision_keyboard(
        message,
        'Chcete odpočítavať obednú prestávku?',
        yes_no_keyboard(yes_label='Áno', no_label='Nie'),
    )


@router.message(WorkTimeStates.waiting_lunch_break_value)
async def work_time_lunch_break_value(message: Message, state: FSMContext, config: Config) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    minutes = parse_lunch_break_minutes(message.text or '')
    if minutes is None:
        await message.answer('Trvanie sa nepodarilo rozpoznat. Zadajte 0 az 180 minut, napriklad: 30, 45 minut alebo 1 hodina.')
        return
    WorkTimeService(config.db_path).save_lunch_break_settings(telegram_id=telegram_id, enabled=minutes > 0, minutes=minutes)
    await _continue_pending_work_time_report(message, state, config, telegram_id=telegram_id)


@router.message(WorkTimeStates.waiting_lunch_break_update_value)
async def work_time_lunch_break_update_value(message: Message, state: FSMContext, config: Config) -> None:
    if is_lunch_break_disable_request(message.text or ''):
        await _preview_lunch_break_update(message, state, enabled=False, minutes=0)
        return
    minutes = parse_lunch_break_minutes(message.text or '')
    if minutes is None:
        await message.answer('Trvanie sa nepodarilo rozpoznat. Zadajte 0 az 180 minut, napriklad: 30, 45 minut alebo 1 hodina.')
        return
    await _preview_lunch_break_update(message, state, enabled=minutes > 0, minutes=minutes)


@router.message(WorkTimeStates.waiting_lunch_break_update_confirm)
async def work_time_lunch_break_update_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_approve_edit_cancel(
        context_name='work_time_lunch_break_update_confirm',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'edit':
        await state.set_state(WorkTimeStates.waiting_lunch_break_update_value)
        await message.answer('Napiste alebo povedzte nove trvanie obednej prestavky v minutach.')
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Zmenu obednej prestavky som zrusil. Nic sa nezmenilo.')
        return
    if decision != 'approve':
        await answer_with_decision_keyboard(message, 'Schvalit zmenu obednej prestavky alebo zrusit?', approve_edit_cancel_keyboard(approve_label='Uložiť', edit_label='Upraviť', cancel_label='Zrušiť'))
        return
    telegram_id = _telegram_id(message)
    data = await state.get_data()
    if telegram_id is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    try:
        minutes = int(data['work_time_lunch_break_minutes'])
        enabled = bool(data['work_time_lunch_break_enabled'])
    except (KeyError, TypeError, ValueError):
        await state.clear()
        await message.answer('Nahlad zmeny uz nie je dostupny. Skuste poziadavku zadat znova.')
        return
    settings = WorkTimeService(config.db_path).save_lunch_break_settings(
        telegram_id=telegram_id,
        enabled=enabled,
        minutes=minutes,
    )
    await state.clear()
    if not settings.enabled:
        await message.answer('Odpočítavanie obednej prestávky je vypnuté. Ďalšie výkazy dochádzky budú bez odpočtu obeda.')
        return
    await message.answer(
        f'Obedná prestávka je nastavená na {settings.minutes} minút. Použije sa pri ďalších výkazoch dochádzky.'
    )

@router.message(WorkTimeStates.waiting_manual_range_input)
async def work_time_manual_range_input(message: Message, state: FSMContext, config: Config) -> None:
    candidate = await _resolve_manual_entry_candidate(message.text or '', config)
    if candidate is None:
        await message.answer('Cas sa nepodarilo rozpoznat. Napiste napr.: dnes od 5:30 do 17:00, dnes 10 hodin, alebo zrusit.')
        return
    await _preview_manual_candidate(message, state, candidate)


@router.message(WorkTimeStates.waiting_close_input)
async def work_time_close_input(message: Message, state: FSMContext, config: Config) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        await state.clear()
        return
    open_day = WorkTimeService(config.db_path).get_open_day(telegram_id=telegram_id)
    if open_day is None:
        await state.clear()
        await message.answer('Otvoreny pracovny den uz nie je dostupny.')
        return
    raw_text = message.text or ''
    candidate = parse_close_candidate(raw_text, open_day=open_day)
    if candidate is not None and candidate.close_mode == 'close_now' and _should_try_llm_work_time_slots(raw_text):
        llm_candidate = await resolve_work_time_entry_candidate(
            user_input_text=raw_text,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
            open_day=open_day,
        )
        if llm_candidate is not None:
            candidate = llm_candidate
    if candidate is None:
        await message.answer('Napiste cas odchodu alebo trvanie, napriklad: o 17:00 alebo 10 hodin.')
        return
    await state.update_data(work_time_close_candidate=_candidate_to_state(candidate), work_time_close_open_day_id=open_day.id)
    await state.set_state(WorkTimeStates.waiting_close_preview_confirm)
    await answer_with_decision_keyboard(
        message,
        'Skontrolujte uzavretie pracovneho dna:\n'
        f'{format_candidate_preview(candidate, open_day=open_day, lunch_break_minutes=_effective_lunch_break_minutes_for_user(config, telegram_id))}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


@router.message(WorkTimeStates.waiting_manual_range_confirm)
async def work_time_manual_range_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_approve_edit_cancel(
        context_name='work_time_manual_range_preview',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'edit':
        await state.set_state(WorkTimeStates.waiting_manual_range_input)
        await message.answer('Napiste opraveny cely rozsah, napriklad: vcera od 6:00 do 16:30.')
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Doplnenie pracovneho casu som zrusil. Nic sa neulozilo.')
        return
    if decision != 'approve':
        await answer_with_decision_keyboard(message, 'Schvalit, upravit alebo zrusit?', approve_edit_cancel_keyboard())
        return
    telegram_id = _telegram_id(message)
    candidate = _candidate_from_state((await state.get_data()).get('work_time_manual_candidate'))
    if telegram_id is None or candidate is None:
        await state.clear()
        await message.answer('Nahlad uz nie je dostupny. Skuste rozsah zadat znova.')
        return
    service = WorkTimeService(config.db_path)
    if candidate.start_time is None and candidate.duration_minutes is not None:
        result = service.add_duration_entry(
            telegram_id=telegram_id,
            candidate=candidate,
            source_message_id=getattr(message, 'message_id', None),
        )
    else:
        result = service.add_manual_range(
            telegram_id=telegram_id,
            candidate=candidate,
            source_message_id=getattr(message, 'message_id', None),
        )
    await state.clear()
    await _answer_work_time_result(message, result, success_prefix='Pracovny cas je ulozeny.')


@router.message(WorkTimeStates.waiting_close_preview_confirm)
async def work_time_close_preview_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_approve_edit_cancel(
        context_name='work_time_close_preview',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'edit':
        await state.set_state(WorkTimeStates.waiting_close_input)
        await message.answer('Napiste opraveny cas odchodu alebo trvanie, napriklad: o 17:00 alebo 10 hodin.')
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Uzavretie pracovneho dna som zrusil. Nic sa nezmenilo.')
        return
    if decision != 'approve':
        await answer_with_decision_keyboard(message, 'Schvalit, upravit alebo zrusit?', approve_edit_cancel_keyboard())
        return
    telegram_id = _telegram_id(message)
    candidate = _candidate_from_state((await state.get_data()).get('work_time_close_candidate'))
    if telegram_id is None or candidate is None:
        await state.clear()
        await message.answer('Nahlad uz nie je dostupny. Skuste uzavretie zadat znova.')
        return
    end_dt = None
    duration = candidate.duration_minutes
    if candidate.end_time is not None:
        end_dt = datetime.combine(candidate.work_date, candidate.end_time)
    result = WorkTimeService(config.db_path).close_open_day(
        telegram_id=telegram_id,
        end_datetime=end_dt,
        duration_minutes=duration,
        source_message_id=getattr(message, 'message_id', None),
    )
    await state.clear()
    await _answer_work_time_result(message, result, success_prefix='Pracovny den je uzavrety.')


@router.message(WorkTimeStates.waiting_open_day_conflict_choice)
async def work_time_open_day_conflict_choice(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_work_time_open_conflict_choice(
        context_name='work_time_open_day_conflict_choice',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision in {'close_day', 'fill_time'}:
        await state.set_state(WorkTimeStates.waiting_close_input)
        await message.answer('Napiste cas odchodu alebo trvanie pre otvoreny den, napriklad: o 17:00 alebo 10 hodin.')
        return
    if decision == 'skip_day':
        telegram_id = _telegram_id(message)
        if telegram_id is None:
            await state.clear()
            await message.answer('Nepodarilo sa identifikovat pouzivatela.')
            return
        result = WorkTimeService(config.db_path).skip_open_day(
            telegram_id=telegram_id,
            source_message_id=getattr(message, 'message_id', None),
        )
        await state.clear()
        await _answer_work_time_result(message, result, success_prefix='Otvoreny den je preskoceny.')
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Otvorenie noveho pracovneho dna som zrusil.')
        return
    await answer_with_decision_keyboard(message, 'Vyberte jednu moznost.', work_time_open_conflict_keyboard())


@router.message(WorkTimeStates.waiting_missing_days_choice)
async def work_time_missing_days_choice(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_work_time_missing_days_choice(
        context_name='work_time_missing_days_choice',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'fill':
        await state.set_state(WorkTimeStates.waiting_manual_range_input)
        await message.answer('Napiste chybajuci den ako rozsah, napriklad: vcera od 6:00 do 16:30.')
        return
    if decision in {'skip', 'cancel'}:
        await state.clear()
        await message.answer('V poriadku, chybajuce dni teraz neriesim.')
        return
    await answer_with_decision_keyboard(message, 'Vyberte jednu moznost.', work_time_missing_days_keyboard())


async def _preview_lunch_break_update(message: Message, state: FSMContext, *, enabled: bool, minutes: int) -> None:
    await state.update_data(
        work_time_lunch_break_enabled=enabled,
        work_time_lunch_break_minutes=minutes,
    )
    await state.set_state(WorkTimeStates.waiting_lunch_break_update_confirm)
    if not enabled or minutes <= 0:
        preview = 'Vypnut odpocitavanie obednej prestavky?'
    else:
        preview = f'Nastavit obednu prestavku na {minutes} minut?'
    await answer_with_decision_keyboard(
        message,
        f'{preview}\n\nSchvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(approve_label='Ulozit', edit_label='Upravit', cancel_label='Zrusit'),
    )


async def _continue_pending_work_time_report(
    message: Message,
    state: FSMContext,
    config: Config,
    *,
    telegram_id: int,
) -> None:
    data = await state.get_data()
    try:
        year = int(data['work_time_pending_report_year'])
        month = int(data['work_time_pending_report_month'])
    except (KeyError, TypeError, ValueError):
        await state.clear()
        await message.answer('Povodna poziadavka na vykaz uz nie je dostupna. Skuste vykaz zadat znova.')
        return
    await _send_work_time_report(message, state, config, telegram_id=telegram_id, year=year, month=month)


async def _send_work_time_report(
    message: Message,
    state: FSMContext,
    config: Config,
    *,
    telegram_id: int,
    year: int,
    month: int,
) -> None:
    result = WorkTimeService(config.db_path).generate_monthly_report(
        telegram_id=telegram_id,
        year=year,
        month=month,
        output_dir=config.storage_dir / 'work_time_reports' / str(telegram_id),
    )
    await state.clear()
    if not result.ok or result.report_path is None:
        await message.answer('Vykaz sa nepodarilo vytvorit.')
        return
    await message.answer_document(
        FSInputFile(result.report_path, filename=result.report_path.name),
        caption='Vytvoril som mesacny vykaz odpracovanych hodin. Nie je to oficialny mzdovy ani pravny HR doklad.',
    )

async def _preview_delete_month(
    message: Message,
    state: FSMContext,
    config: Config,
    *,
    year: int,
    month: int,
) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    summary = WorkTimeService(config.db_path).summarize_month(telegram_id=telegram_id, year=year, month=month)
    if summary.row_count == 0:
        await state.clear()
        await message.answer(f'Za {summary.month:02d}/{summary.year} nie su ulozene ziadne zaznamy dochadzky. Nie je co vymazat.')
        return
    await state.update_data(
        work_time_delete_month_year=year,
        work_time_delete_month_month=month,
        work_time_delete_month_row_count=summary.row_count,
        work_time_delete_month_total_minutes=summary.total_minutes,
    )
    await state.set_state(WorkTimeStates.waiting_delete_month_confirm)
    await answer_with_decision_keyboard(
        message,
        'POZOR: vymazete ulozene zaznamy dochadzky pre tento mesiac.\n'
        f'{format_month_summary(summary)}\n\n'
        'Vymazu sa iba DB zaznamy dochadzky aktualneho pouzivatela/workspace pre tento mesiac. '
        'Mesacne Excel vykazy vytvorene na poziadanie nie su kanonicke data.\n\n'
        'Vymazat alebo zrusit?',
        delete_cancel_keyboard(delete_label='Vymazat dochadzku', cancel_label='Zrusit'),
    )


async def _resolve_manual_entry_candidate(text: str, config: Config) -> WorkTimeCandidate | None:
    candidate = parse_manual_range_candidate(text) or parse_duration_entry_candidate(text)
    if candidate is not None:
        return candidate
    return await resolve_work_time_entry_candidate(
        user_input_text=text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )


def _effective_lunch_break_minutes_for_user(config: Config, telegram_id: int | None) -> int:
    if telegram_id is None:
        return 0
    settings = WorkTimeService(config.db_path).get_lunch_break_settings(telegram_id=telegram_id)
    if not settings.configured or not settings.enabled:
        return 0
    return settings.minutes

def _should_try_llm_work_time_slots(text: str) -> bool:
    lowered = (text or '').casefold()
    if any(term in lowered for term in ('teraz', 'now')):
        return False
    return len(lowered.split()) > 2


async def _preview_manual_candidate(message: Message, state: FSMContext, candidate: WorkTimeCandidate) -> None:
    await state.update_data(work_time_manual_candidate=_candidate_to_state(candidate))
    await state.set_state(WorkTimeStates.waiting_manual_range_confirm)
    await answer_with_decision_keyboard(
        message,
        'Skontrolujte doplnenie pracovneho casu:\n'
        f'{format_candidate_preview(candidate, lunch_break_minutes=_effective_lunch_break_minutes_for_user(config, _telegram_id(message)))}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


async def _answer_work_time_result(message: Message, result, *, success_prefix: str) -> None:
    if result.ok and result.day is not None:
        await message.answer(f'{success_prefix}\n{format_day_summary(result.day)}')
        return
    if result.reason == 'conflict_same_day' and result.conflict_day is not None:
        await message.answer(f'Tento den uz ma zaznam: {format_day_summary(result.conflict_day)}. Jedna zmena denne je limit MVP.')
        return
    if result.reason == 'end_before_start':
        await message.answer('Odchod nemoze byt skor ako prichod. Praca cez polnoc je mimo tohto MVP.')
        return
    if result.reason == 'no_open_day':
        await message.answer('Nemate otvoreny pracovny den.')
        return
    await message.answer('Operacia sa nepodarila bezpecne ulozit.')


def _telegram_id(message: Message) -> int | None:
    return getattr(getattr(message, 'from_user', None), 'id', None)


def _candidate_to_state(candidate: WorkTimeCandidate) -> dict[str, object]:
    return {
        'work_date': candidate.work_date.isoformat(),
        'start_time': candidate.start_time.strftime('%H:%M') if candidate.start_time else None,
        'end_time': candidate.end_time.strftime('%H:%M') if candidate.end_time else None,
        'duration_minutes': candidate.duration_minutes,
        'close_mode': candidate.close_mode,
        'needs_confirmation': candidate.needs_confirmation,
    }


def _candidate_from_state(value: object) -> WorkTimeCandidate | None:
    if not isinstance(value, dict):
        return None
    try:
        from datetime import date

        start_raw = value.get('start_time')
        end_raw = value.get('end_time')
        return WorkTimeCandidate(
            work_date=date.fromisoformat(str(value['work_date'])),
            start_time=_parse_hhmm(start_raw) if isinstance(start_raw, str) else None,
            end_time=_parse_hhmm(end_raw) if isinstance(end_raw, str) else None,
            duration_minutes=int(value['duration_minutes']) if value.get('duration_minutes') is not None else None,
            close_mode=str(value.get('close_mode') or 'unknown'),
            needs_confirmation=bool(value.get('needs_confirmation', True)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(':', 1)
    return time(hour=int(hour), minute=int(minute))
