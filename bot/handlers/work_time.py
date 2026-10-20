from __future__ import annotations

from datetime import UTC, date, datetime, time
from dataclasses import asdict
import logging
import sqlite3
import re
from types import SimpleNamespace

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

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
from bot.services.supplier_service import SupplierService
from bot.services.workspace_context import WorkspaceContextError, WorkspaceContextService
from bot.services.work_time import (
    WorkTimeCandidate,
    WorkTimeBoundaryChange,
    WorkTimeDayBreakChange,
    WorkTimeDay,
    WorkTimeLunchBreakSettings,
    WorkTimeService,
    format_candidate_preview,
    format_day_summary,
    day_break_eligible,
    day_calculation,
    format_closed_day_summary,
    resolve_day_break_slots,
    format_month_summary,
    is_lunch_break_disable_request,
    parse_close_candidate,
    parse_duration_entry_candidate,
    parse_explicit_month,
    parse_lunch_break_minutes,
    parse_manual_range_candidate,
    parse_open_start_candidate,
    parse_report_month,
    resolve_work_time_entry_candidate,
    work_time_local_date,
    work_time_local_now,
)


router = Router(name='work_time')

_WORK_TIME_WORKSPACE_ID_KEY = 'work_time_workspace_id'
_BOUNDARY_CHANGE_KEY = 'work_time_boundary_change'
WORK_TIME_REPORT_CHOICE_KEY = 'work_time_report_choice_keyboard'
DAY_BREAK_FLOW_KEY = 'work_time_day_break_flow'
DAY_BREAK_CHANGE_KEY = 'work_time_day_break_change'
_LOG = logging.getLogger(__name__)


def _resolve_work_time_workspace_id(config: Config, telegram_id: int) -> str | None:
    if not config.db_path.exists():
        return None
    try:
        return WorkspaceContextService(config.db_path).resolve_for_user(telegram_id).workspace_id
    except WorkspaceContextError as workspace_error:
        try:
            supplier = SupplierService(config.db_path).get_by_telegram_id(telegram_id)
        except RuntimeError:
            raise workspace_error
        if supplier is None or supplier.workspace_id is None:
            return None
        raise workspace_error


async def _require_work_time_service(
    message: Message,
    state: FSMContext,
    config: Config,
) -> WorkTimeService:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        return WorkTimeService(config.db_path)
    data = await state.get_data()
    if _WORK_TIME_WORKSPACE_ID_KEY not in data:
        try:
            workspace_id = _resolve_work_time_workspace_id(config, telegram_id)
        except WorkspaceContextError:
            await state.clear()
            await message.answer(
                'Aktívny business profil pre evidenciu času nie je dostupný alebo nie je vybraný.',
                reply_markup=ReplyKeyboardRemove(),
            )
            raise RuntimeError('work_time_workspace_context_required')
        await state.update_data(**{_WORK_TIME_WORKSPACE_ID_KEY: workspace_id or ''})
    else:
        workspace_id = str(data.get(_WORK_TIME_WORKSPACE_ID_KEY) or '').strip() or None
        if workspace_id is not None:
            try:
                WorkspaceContextService(config.db_path).require_membership(
                    telegram_id,
                    workspace_id,
                )
            except WorkspaceContextError as exc:
                await state.clear()
                await message.answer(
                    'Business profil tejto evidencie času už nie je dostupný.',
                    reply_markup=ReplyKeyboardRemove(),
                )
                raise RuntimeError('work_time_workspace_membership_required') from exc
    return WorkTimeService(config.db_path, workspace_id=workspace_id)


async def _work_time_report_storage_key(
    message: Message,
    state: FSMContext,
    config: Config,
) -> str:
    telegram_id = _telegram_id(message)
    data = await state.get_data()
    workspace_id = str(data.get(_WORK_TIME_WORKSPACE_ID_KEY) or '').strip()
    if telegram_id is not None and workspace_id:
        return WorkspaceContextService(config.db_path).require_membership(
            telegram_id,
            workspace_id,
        ).storage_key
    return str(telegram_id or 'legacy')


class WorkTimeStates(StatesGroup):
    waiting_lunch_scope = State()
    waiting_day_break_date = State()
    waiting_day_break_minutes = State()
    waiting_day_break_confirm = State()
    waiting_open_preview_confirm = State()
    waiting_open_input = State()
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


def _owns_report_choice(message, data: dict) -> bool:
    ref = data.get(WORK_TIME_REPORT_CHOICE_KEY)
    if not isinstance(ref, dict):
        return False
    return (
        isinstance(ref.get('message_id'), int)
        and isinstance(ref.get('chat_id'), int)
        and isinstance(ref.get('owner_id'), int)
        and ref['owner_id'] == getattr(getattr(message, 'from_user', None), 'id', None)
        and ref['chat_id'] == getattr(getattr(message, 'chat', None), 'id', None)
        and ref.get('workspace_id') == data.get(_WORK_TIME_WORKSPACE_ID_KEY)
    )


async def clear_work_time_report_choice_keyboard(*, message, state: FSMContext) -> None:
    data = await state.get_data()
    if not _owns_report_choice(message, data):
        return
    bot = getattr(message, 'bot', None)
    if bot is None:
        return
    ref = data[WORK_TIME_REPORT_CHOICE_KEY]
    try:
        await bot.edit_message_reply_markup(
            chat_id=ref['chat_id'], message_id=ref['message_id'], reply_markup=None,
        )
    except Exception:
        _LOG.exception('Failed to clear work-time report choice inline keyboard')
        return
    await state.update_data(**{WORK_TIME_REPORT_CHOICE_KEY: None})


async def is_current_work_time_report_choice(callback, state: FSMContext) -> bool:
    data = await state.get_data()
    source = callback.message
    if source is None or not getattr(getattr(source, 'from_user', None), 'is_bot', False):
        return False
    # Callback actor is the human; the source message was authored by the bot.
    actor_message = SimpleNamespace(from_user=callback.from_user, chat=source.chat)
    return (
        _owns_report_choice(actor_message, data)
        and data[WORK_TIME_REPORT_CHOICE_KEY]['message_id'] == source.message_id
    )


async def _ask_report_lunch_choice(message, state: FSMContext) -> None:
    data = await state.get_data()
    text = 'Chcete odpočítavať obednú prestávku?'
    if isinstance(data.get(WORK_TIME_REPORT_CHOICE_KEY), dict):
        # Unknown keeps the one current card, rather than creating old live copies.
        await message.answer(text)
        return
    sent = await answer_with_decision_keyboard(message, text, yes_no_keyboard(yes_label='Áno', no_label='Nie'))
    message_id = getattr(sent, 'message_id', None)
    chat_id = getattr(getattr(sent, 'chat', None), 'id', None)
    owner_id = _telegram_id(message)
    if isinstance(message_id, int) and isinstance(chat_id, int) and owner_id is not None:
        await state.update_data(**{WORK_TIME_REPORT_CHOICE_KEY: {
            'message_id': message_id, 'chat_id': chat_id, 'owner_id': owner_id,
            'workspace_id': data.get(_WORK_TIME_WORKSPACE_ID_KEY),
        }})


@router.message(Command('dochadzka'))
async def cmd_dochadzka(message: Message, state: FSMContext, config: Config) -> None:
    if (await state.get_data()).get(DAY_BREAK_FLOW_KEY):
        await finish_day_break_flow(message=message, state=state, config=config)
    await clear_work_time_report_choice_keyboard(message=message, state=state)
    await state.clear()
    await message.answer(
        'Evidencia pracovneho casu je ciastocny OfficeFlow modul.\n\n'
        'Mozete napisat napriklad:\n'
        '- zacinam pracovny den\n'
        '- zatvor den o 17:00\n'
        '- zatvor den 10 hodin\n'
        '- oprav dnesny prichod na 06:54\n'
        '- oprav odchod 9.9.2026 na 13:10\n'
        '- pracoval som dnes od 5:30 do 17:00\n'
        '- vytvor vykaz hodin za jun 2026\n'
        '- nastav obednu prestavku na 30 minut\n'
        '- vymaz dochadzku za jul 2026\n\n'
        'Vykaz pocita ciste hodiny po nastavenej obednej prestavke. '
        'Oprava ulozeneho casu vyzaduje kontrolu povodneho a noveho rozsahu a potvrdenie. '
        'Po uzavretí vidíte interval, odpočítanú prestávku a čisté hodiny; bot čaká na ďalšiu požiadavku. '
        'Ak je úprava prestávky jedného dňa zapnutá, použite Upraviť dnešnú prestávku alebo zadajte dátum a nové minúty (aj 0). '
        'Zmenu najprv potvrdíte; obvyklé nastavenie aj ostatné dni zostanú zachované. '
        'Pevné čisté hodiny týmto editorom nemeníme. Zmena obvyklého odpočtu môže prepočítať staršie dni bez vlastnej výnimky. '
        'Nie je to mzdova dochadzka, vypocet mzdy ani pravny HR doklad.',
        reply_markup=ReplyKeyboardRemove(),
    )


async def start_open_work_day(
    message: Message,
    state: FSMContext,
    config: Config,
    *,
    text: str,
) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    service = await _require_work_time_service(message, state, config)
    explicit_candidate = await _resolve_open_candidate(text, config)
    if explicit_candidate is not None:
        if not _is_valid_explicit_open_candidate(explicit_candidate):
            await state.set_state(WorkTimeStates.waiting_open_input)
            await message.answer(
                'Cas prichodu nemoze byt v buducnosti. Napiste dnesny cas prichodu, napriklad: 7:10.'
            )
            return
        await _preview_open_candidate(message, state, config, explicit_candidate)
        return
    if _contains_clock_like_value(text):
        await state.set_state(WorkTimeStates.waiting_open_input)
        await message.answer(
            'Cas prichodu sa nepodarilo bezpecne overit. Napiste ho vo formate HH:MM, napriklad: 7:10.'
        )
        return
    result = service.open_day(
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
    await message.answer('Dnesny den uz ma zaznam. Na opravu zadajte presny cas prichodu alebo odchodu; zmenu najprv potvrdite.')


async def start_close_work_day(message: Message, state: FSMContext, config: Config, *, text: str) -> None:
    await _start_or_continue_close(message, state, config, text=text, continuation=False)


async def _start_or_continue_close(
    message: Message, state: FSMContext, config: Config, *, text: str, continuation: bool,
) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    service = (await _require_work_time_service(message, state, config))
    data = await state.get_data()
    target_date = data.get('work_time_close_target_date') if continuation else None
    open_day = service.get_day(telegram_id=telegram_id, work_date=target_date) if isinstance(target_date, str) else (
        service.get_open_day(telegram_id=telegram_id)
        or service.get_day(telegram_id=telegram_id, work_date=work_time_local_date().isoformat())
    )
    candidate = await _resolve_close_candidate(text, config, open_day)
    if candidate is not None and candidate.close_mode == 'close_at_time':
        selected_day = service.get_day(telegram_id=telegram_id, work_date=candidate.work_date.isoformat())
        if selected_day is not None:
            await _preview_close_candidate(message, state, config, candidate, selected_day)
            return
        await state.clear()
        await message.answer('Pre tento datum nie je ulozeny pracovny den. Nic sa nezmenilo.', reply_markup=ReplyKeyboardRemove())
        return
    if open_day is None:
        if continuation:
            await state.clear()
            await message.answer('Otvoreny pracovny den uz nie je dostupny.', reply_markup=ReplyKeyboardRemove())
            return
        manual_candidate = await _resolve_manual_entry_candidate(text, config)
        if manual_candidate is not None:
            await _preview_manual_candidate(message, state, config, manual_candidate)
            return
        await state.clear()
        await message.answer('Nemate otvoreny pracovny den. Ak chcete doplnit den spatne, napiste napriklad: pracoval som dnes od 5:30 do 17:00 alebo dnes 10 hodin.')
        return

    if candidate is None or open_day.status != 'open':
        await state.update_data(work_time_close_target_date=open_day.work_date)
        await state.set_state(WorkTimeStates.waiting_close_input)
        await message.answer(
            'Napiste presny cas odchodu, napriklad: 17:00. Uzavrety den opravim iba po potvrdeni presneho casu.'
            if open_day.status == 'closed'
            else 'Napiste cas odchodu alebo trvanie, napriklad: 17:00, o 17:00 alebo 10 hodin.'
        )
        return
    if candidate.close_mode == 'close_now':
        result = service.close_open_day(
            telegram_id=telegram_id,
            source_message_id=getattr(message, 'message_id', None),
        )
        await state.clear()
        await _answer_work_time_result(message, result, success_prefix='Pracovny den je uzavrety.', config=config)
        return

    await _preview_close_candidate(message, state, config, candidate, open_day)


async def start_add_work_time_entry(message: Message, state: FSMContext, config: Config, *, text: str) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    service = await _require_work_time_service(message, state, config)
    open_day = service.get_open_day(telegram_id=telegram_id)
    if open_day is not None:
        close_candidate = await _resolve_close_candidate(text, config, open_day)
        if close_candidate is not None:
            if close_candidate.close_mode == 'close_now':
                result = service.close_open_day(
                    telegram_id=telegram_id,
                    source_message_id=getattr(message, 'message_id', None),
                )
                await state.clear()
                await _answer_work_time_result(message, result, success_prefix='Pracovny den je uzavrety.', config=config)
                return
            await _preview_close_candidate(message, state, config, close_candidate, open_day)
            return
    candidate = await _resolve_manual_entry_candidate(text, config)
    if candidate is None:
        await state.set_state(WorkTimeStates.waiting_manual_range_input)
        await message.answer('Napiste rozsah alebo pocet hodin, napriklad: pracoval som dnes od 5:30 do 17:00 alebo dnes 10 hodin.')
        return
    await _preview_manual_candidate(message, state, config, candidate)


async def start_generate_work_time_report(
    message: Message,
    state: FSMContext,
    config: Config,
    *,
    text: str,
    source_channel: str = 'text',
    report_period: dict[str, object] | None = None,
) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    if report_period is None:
        year, month = parse_report_month(text)
    else:
        selected_period = _resolve_report_period_slot(report_period)
        if selected_period is None:
            await message.answer('Mesiac vykazu sa nepodarilo overit. Napiste napriklad: vykaz za maj 2026 alebo vykaz za tento mesiac.')
            return
        year, month = selected_period
    service = (await _require_work_time_service(message, state, config))
    settings = service.get_lunch_break_settings(telegram_id=telegram_id)
    if not settings.configured:
        await state.update_data(
            work_time_pending_report_year=year,
            work_time_pending_report_month=month,
            work_time_pending_report_source_channel=source_channel,
        )
        await state.set_state(WorkTimeStates.waiting_lunch_break_initial_choice)
        await _ask_report_lunch_choice(message, state)
        return
    await _send_work_time_report(message, state, config, telegram_id=telegram_id, year=year, month=month)


async def start_update_work_time_lunch_break(message: Message, state: FSMContext, config: Config, *, text: str,
                                           break_slots: dict | None = None) -> None:
    telegram_id = _telegram_id(message)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    if break_slots is not None or config.work_time_day_break_enabled:
        from bot.services.authorization import is_authorized_telegram_user
        if not is_authorized_telegram_user(config, telegram_id):
            return
        slots = break_slots if break_slots is not None else await resolve_day_break_slots(
            user_input_text=text, api_key=config.openai_api_key, model=config.openai_llm_model)
        await _continue_break_request(message, state, config, slots)
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


async def _day_break_service(message, state, config) -> WorkTimeService:
    from bot.services.authorization import is_authorized_telegram_user
    if not is_authorized_telegram_user(config, _telegram_id(message)):
        raise RuntimeError('work_time_access_required')
    service = await _require_work_time_service(message, state, config)
    if _resolve_work_time_workspace_id(config, _telegram_id(message)) != service.workspace_id:
        raise RuntimeError('work_time_active_workspace_changed')
    return service


async def _set_day_break_state(state, value):
    await state.set_state(value)
    from bot.services.active_fsm_guard import touch_active_fsm_activity
    await touch_active_fsm_activity(state)


async def send_closed_day_summary(message, config, day, *, prefix='✅ Pracovný deň je uzavretý.', service=None):
    """Presentation only: never enter FSM while displaying the optional launcher."""
    service = service or WorkTimeService(config.db_path, workspace_id=_resolve_work_time_workspace_id(config, _telegram_id(message)))
    current = service.get_day(telegram_id=_telegram_id(message), work_date=day.work_date)
    if current is None or current.id != day.id:
        return
    settings = service.get_lunch_break_settings(telegram_id=_telegram_id(message))
    try:
        await message.answer(f'{prefix}\n{format_closed_day_summary(current, settings)}', reply_markup=ReplyKeyboardRemove())
        if config.work_time_day_break_enabled and service.day_break_schema_ready() and day_break_eligible(current):
            fingerprint = service.day_break_fingerprint(telegram_id=_telegram_id(message), work_date=current.work_date)
            label = ('Upraviť dnešnú prestávku' if current.work_date == work_time_local_date().isoformat()
                     else f'Upraviť prestávku · {date.fromisoformat(current.work_date):%d.%m.%Y}')
            await message.answer('Zmena sa bude týkať iba tohto dňa.', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=label, callback_data=f'wtb:{current.id}:{current.work_date.replace("-", "")}:{fingerprint}')]]))
    except Exception:
        _LOG.exception('Work-time summary/keyboard delivery failed after committed operation')


async def _continue_break_request(message, state, config, slots):
    if await state.get_state() is not None and not (await state.get_data()).get(DAY_BREAK_FLOW_KEY):
        await message.answer('Najprv dokončite alebo zrušte aktuálnu akciu.')
        return
    slots = slots if isinstance(slots, dict) else {}
    raw_scope = slots.get('scope')
    slots = {'scope': raw_scope if isinstance(raw_scope, str) and raw_scope in {'day', 'default', 'unknown'} else 'unknown',
             'work_date': slots.get('work_date') if isinstance(slots.get('work_date'), str) else None,
             'minutes': slots.get('minutes')}
    service = await _day_break_service(message, state, config)
    data = await state.get_data()
    bound = data.get(DAY_BREAK_FLOW_KEY) or {}
    scope = bound.get('scope') or slots.get('scope')
    if slots.get('scope') not in {None, scope, 'unknown'} or (bound.get('scope') and slots.get('scope') == 'unknown'):
        await message.answer('Pokračujte v oprave vybraného dňa alebo použite /cancel.', reply_markup=ReplyKeyboardRemove())
        return
    minutes = slots.get('minutes', bound.get('minutes'))
    if minutes is None:
        minutes = bound.get('minutes')
    if type(minutes) is not int or not 0 <= minutes <= 180:
        minutes = None
    selected = bound.get('work_date') or slots.get('work_date')
    if bound.get('work_date') and slots.get('work_date') not in {None, bound['work_date']}:
        await message.answer('Dátum tejto opravy zostáva nezmenený. Na inú opravu použite /cancel.', reply_markup=ReplyKeyboardRemove())
        return
    flow = {'scope': scope if scope in {'day', 'default'} else None, 'work_date': selected,
            'minutes': minutes, 'actor': _telegram_id(message), 'workspace': service.workspace_id}
    await state.update_data(**{DAY_BREAK_FLOW_KEY: flow})
    if scope not in {'day', 'default'}:
        await _set_day_break_state(state, WorkTimeStates.waiting_lunch_scope)
        await message.answer('Chcete zmeniť prestávku iba za konkrétny deň, alebo obvyklé nastavenie? Napíšte aj dátum, ak ide o jeden deň.', reply_markup=ReplyKeyboardRemove())
        return
    if scope == 'default':
        if selected is not None:
            await message.answer('Pre obvyklé nastavenie nezadávajte dátum. Použite /cancel a zadajte požiadavku znova.', reply_markup=ReplyKeyboardRemove())
            await _set_day_break_state(state, WorkTimeStates.waiting_lunch_scope)
            return
        if minutes is None:
            await _set_day_break_state(state, WorkTimeStates.waiting_day_break_minutes)
            await message.answer('Zadajte obvyklú prestávku v minútach (0–180).', reply_markup=ReplyKeyboardRemove())
            return
        await _preview_lunch_break_update(message, state, enabled=minutes > 0, minutes=minutes)
        return
    if not config.work_time_day_break_enabled or not service.day_break_schema_ready():
        await state.clear()
        await message.answer('Úprava prestávky jedného dňa zatiaľ nie je zapnutá. Obvyklé nastavenie som nezmenil.', reply_markup=ReplyKeyboardRemove())
        return
    try:
        selected_date = date.fromisoformat(selected) if isinstance(selected, str) else None
        if selected_date and selected_date > work_time_local_date():
            selected_date = None
    except ValueError:
        selected_date = None
    if selected_date is None:
        await state.update_data(**{DAY_BREAK_FLOW_KEY: {**flow, 'work_date': None}})
        await _set_day_break_state(state, WorkTimeStates.waiting_day_break_date)
        await message.answer('Za ktorý deň chcete opraviť prestávku? Zadajte dátum alebo povedzte dnes.', reply_markup=ReplyKeyboardRemove())
        return
    day = service.get_day(telegram_id=_telegram_id(message), work_date=selected_date.isoformat())
    if day is None or not day_break_eligible(day):
        await state.clear()
        await message.answer('Pre tento dátum nemám uzavretý deň s upraviteľným časovým intervalom. Potvrdené čisté hodiny nemením.', reply_markup=ReplyKeyboardRemove())
        return
    if minutes is None:
        await _set_day_break_state(state, WorkTimeStates.waiting_day_break_minutes)
        await message.answer(f'{selected_date:%d.%m.%Y}: zadajte prestávku v minútach (0–180); 0 znamená bez odpočtu.', reply_markup=ReplyKeyboardRemove())
        return
    change = service.prepare_day_break_change(telegram_id=_telegram_id(message), work_date=selected_date.isoformat(), minutes=minutes)
    if change is None:
        await state.update_data(**{DAY_BREAK_FLOW_KEY: {**flow, 'minutes': None}})
        await _set_day_break_state(state, WorkTimeStates.waiting_day_break_minutes)
        await message.answer('Prestávka nesmie byť dlhšia než pracovný interval. Zadajte platné minúty.', reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data(**{DAY_BREAK_CHANGE_KEY: asdict(change), 'work_time_day_break_preview_at': datetime.now(UTC).isoformat()})
    await _set_day_break_state(state, WorkTimeStates.waiting_day_break_confirm)
    _, old_pause, old_net = day_calculation(change.original, change.settings)
    _, new_pause, new_net = day_calculation(change.proposed, change.settings)
    preview = (f'Skontrolujte prestávku za {selected_date:%d.%m.%Y}:\n'
        f'Príchod–odchod: {day.start_time}–{day.end_time}\n'
        f'Prestávka: {old_pause} → {new_pause} min\n'
        f'Odpracované: {old_net // 60}:{old_net % 60:02d} → {new_net // 60}:{new_net % 60:02d}\n'
        'Obvyklé nastavenie aj ostatné dni zostanú nezmenené.\nSchváliť, upraviť alebo zrušiť?')
    await state.update_data(work_time_day_break_preview=preview)
    await message.answer(preview, reply_markup=_boundary_keyboard())
    from bot.services.active_fsm_guard import touch_active_fsm_activity
    await touch_active_fsm_activity(state)


@router.message(StateFilter(WorkTimeStates.waiting_lunch_scope, WorkTimeStates.waiting_day_break_date, WorkTimeStates.waiting_day_break_minutes))
async def work_time_day_break_input(message: Message, state: FSMContext, config: Config):
    flow = (await state.get_data()).get(DAY_BREAK_FLOW_KEY) or {}
    original_state = await state.get_state()
    try:
        await _day_break_service(message, state, config)
        slots = await resolve_day_break_slots(user_input_text=message.text or '', api_key=config.openai_api_key,
            model=config.openai_llm_model, scope=flow.get('scope'), work_date=flow.get('work_date'))
        if await state.get_state() != original_state or (await state.get_data()).get(DAY_BREAK_FLOW_KEY) != flow:
            return
        await _continue_break_request(message, state, config, slots)
    except (RuntimeError, sqlite3.Error):
        await finish_day_break_flow(message=message, state=state, config=config, text='Oprava už nie je dostupná. Nič som nezmenil.')


def _day_break_change_from_state(value):
    try:
        return WorkTimeDayBreakChange(WorkTimeDay(**value['original']), WorkTimeDay(**value['proposed']),
            WorkTimeLunchBreakSettings(**value['settings']), value['revision'])
    except (KeyError, TypeError, ValueError):
        return None


async def finish_day_break_flow(*, message, state, config, text=None):
    data = await state.get_data()
    flow = data.get(DAY_BREAK_FLOW_KEY) or {}
    text = text or ('Opravu prestávky som zrušil. Deň zostal uložený.' if flow.get('scope') == 'day'
                    else 'Úpravu prestávky som zrušil. Nič som nezmenil.')
    service = day = None
    try:
        service = await _day_break_service(message, state, config)
        if flow.get('actor') == _telegram_id(message) and flow.get('work_date'):
            day = service.get_day(telegram_id=_telegram_id(message), work_date=flow['work_date'])
    except (RuntimeError, sqlite3.Error):
        _LOG.warning('Day-break recovery context is no longer accessible')
    await state.clear()
    try:
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        if day is not None and day.status == 'closed':
            await send_closed_day_summary(message, config, day, service=service, prefix='Uložený pracovný deň:')
    except Exception:
        _LOG.exception('Day-break terminal keyboard/result delivery failed')


@router.message(WorkTimeStates.waiting_day_break_confirm)
async def work_time_day_break_confirm(message: Message, state: FSMContext, config: Config):
    data = await state.get_data()
    try:
        await _day_break_service(message, state, config)
        expiry = datetime.fromisoformat(data['work_time_day_break_preview_at'])
        if not 0 <= (datetime.now(UTC) - expiry).total_seconds() <= 900:
            raise ValueError('expired')
    except (ValueError, KeyError, TypeError, RuntimeError, sqlite3.Error):
        await finish_day_break_flow(message=message, state=state, config=config, text='Náhľad opravy vypršal. Nič som nezmenil.')
        return
    decision = await resolve_approve_edit_cancel(context_name='work_time_day_lunch_break_confirm',
        user_input_text=message.text or '', api_key=config.openai_api_key, model=config.openai_llm_model)
    current_data = await state.get_data()
    if (await state.get_state() != WorkTimeStates.waiting_day_break_confirm.state
        or current_data.get(DAY_BREAK_CHANGE_KEY) != data.get(DAY_BREAK_CHANGE_KEY)
        or current_data.get('work_time_day_break_preview_at') != data.get('work_time_day_break_preview_at')):
        return
    if decision == 'cancel':
        await finish_day_break_flow(message=message, state=state, config=config)
        return
    if decision == 'edit':
        flow = data.get(DAY_BREAK_FLOW_KEY) or {}
        await state.update_data(**{DAY_BREAK_FLOW_KEY: {**flow, 'minutes': None}, DAY_BREAK_CHANGE_KEY: None})
        await _set_day_break_state(state, WorkTimeStates.waiting_day_break_minutes)
        await message.answer('Zadajte novú prestávku pre ten istý deň (0–180 minút).', reply_markup=ReplyKeyboardRemove())
        return
    if decision != 'approve':
        await message.answer(data.get('work_time_day_break_preview', 'Použite /cancel.'), reply_markup=_boundary_keyboard())
        return
    change = _day_break_change_from_state(data.get(DAY_BREAK_CHANGE_KEY))
    try:
        service = await _day_break_service(message, state, config)
        flow = data.get(DAY_BREAK_FLOW_KEY) or {}
        if (change is None or not config.work_time_day_break_enabled or flow.get('actor') != _telegram_id(message)
            or flow.get('workspace') != service.workspace_id or flow.get('work_date') != change.original.work_date):
            raise RuntimeError('invalid_day_break_context')
        result = service.apply_day_break_change(telegram_id=_telegram_id(message), change=change,
            source_message_id=getattr(message, 'message_id', None))
        if not result.ok:
            await message.answer('Záznam alebo nastavenie sa zmenilo. Skontrolujte nový náhľad; zatiaľ som nič neprepísal.', reply_markup=ReplyKeyboardRemove())
            await _continue_break_request(message, state, config, {'scope': 'day'})
            return
        await state.clear()
        await send_closed_day_summary(message, config, result.day, service=service, prefix='✅ Prestávka tohto dňa je uložená.')
    except (RuntimeError, sqlite3.Error):
        _LOG.exception('Day-break correction failed')
        await finish_day_break_flow(message=message, state=state, config=config, text='Opravu sa nepodarilo bezpečne uložiť. Skontrolujte záznam.')


@router.callback_query(F.data.startswith('wtb:'))
async def work_time_day_break_callback(callback: CallbackQuery, state: FSMContext, config: Config):
    from bot.services.authorization import is_authorized_telegram_user
    actor = getattr(callback.from_user, 'id', None)
    source = callback.message
    sender = getattr(source, 'from_user', None)
    if not is_authorized_telegram_user(config, actor):
        await callback.answer('Prístup nie je povolený.', show_alert=True)
        return
    match = re.fullmatch(r'wtb:([0-9]{1,19}):([0-9]{8}):([0-9a-f]{24})', callback.data or '')
    if (not match or source is None or getattr(getattr(source, 'chat', None), 'type', None) != 'private'
        or source.chat.id != actor or not getattr(sender, 'is_bot', False)
        or sender.id != getattr(getattr(source, 'bot', None), 'id', None)):
        await callback.answer('Toto tlačidlo už nie je dostupné.', show_alert=True)
        return
    if await state.get_state() is not None:
        await callback.answer('Najprv dokončite alebo zrušte aktuálnu akciu.', show_alert=True)
        return
    try:
        selected = datetime.strptime(match[2], '%Y%m%d').date().isoformat()
        workspace = _resolve_work_time_workspace_id(config, actor)
        service = WorkTimeService(config.db_path, workspace_id=workspace)
        day = service.get_day(telegram_id=actor, work_date=selected)
        if day is None or day.id != int(match[1]):
            await callback.answer('Deň nie je dostupný v aktívnom profile.', show_alert=True)
            return
        stale = service.day_break_fingerprint(telegram_id=actor, work_date=selected) != match[3]
        try:
            await source.bot.edit_message_reply_markup(chat_id=source.chat.id, message_id=source.message_id, reply_markup=None)
        except Exception:
            _LOG.exception('Day-break launcher cleanup failed')
        from bot.handlers.decision_callbacks import _CallbackMessageAdapter
        message = _CallbackMessageAdapter(callback)
        if stale or not day_break_eligible(day) or not config.work_time_day_break_enabled or not service.day_break_schema_ready():
            await callback.answer('Údaje sa zmenili alebo úprava nie je dostupná.', show_alert=True)
            await send_closed_day_summary(message, config, day, service=service, prefix='Aktuálny uložený deň:')
            return
        await callback.answer()
        await _continue_break_request(message, state, config, {'scope': 'day', 'work_date': selected})
        from bot.services.active_fsm_guard import touch_active_fsm_activity
        await touch_active_fsm_activity(state)
    except (RuntimeError, sqlite3.Error, ValueError):
        _LOG.exception('Day-break launcher context rejected')
        await callback.answer('Tlačidlo nie je dostupné. Zadajte požiadavku znova.', show_alert=True)


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

    summary = (await _require_work_time_service(message, state, config)).delete_month(
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
        await clear_work_time_report_choice_keyboard(message=message, state=state)
        await state.clear()
        await message.answer('Nepodarilo sa identifikovat pouzivatela.')
        return
    if decision == 'no':
        await clear_work_time_report_choice_keyboard(message=message, state=state)
        (await _require_work_time_service(message, state, config)).save_lunch_break_settings(telegram_id=telegram_id, enabled=False, minutes=0)
        await _continue_pending_work_time_report(message, state, config, telegram_id=telegram_id)
        return
    if decision == 'yes':
        await clear_work_time_report_choice_keyboard(message=message, state=state)
        await state.set_state(WorkTimeStates.waiting_lunch_break_value)
        await message.answer('Napíšte alebo povedzte trvanie obednej prestávky v minútach.', reply_markup=ReplyKeyboardRemove())
        return
    await _ask_report_lunch_choice(message, state)


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
    (await _require_work_time_service(message, state, config)).save_lunch_break_settings(telegram_id=telegram_id, enabled=minutes > 0, minutes=minutes)
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
    settings = (await _require_work_time_service(message, state, config)).save_lunch_break_settings(
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
    await _preview_manual_candidate(message, state, config, candidate)


@router.message(WorkTimeStates.waiting_open_input)
async def work_time_open_input(message: Message, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    change = _boundary_change_from_state(data.get(_BOUNDARY_CHANGE_KEY))
    bound_day = change.original if change else None
    if bound_day is None and isinstance(data.get('work_time_open_target_date'), str):
        bound_day = (await _require_work_time_service(message, state, config)).get_day(
            telegram_id=_telegram_id(message), work_date=data['work_time_open_target_date'],
        )
    candidate = await _resolve_open_candidate(message.text or '', config, bound_day=bound_day)
    if candidate is None or not _is_valid_explicit_open_candidate(candidate):
        await state.set_state(WorkTimeStates.waiting_open_input)
        await message.answer(
            'Cas prichodu sa nepodarilo overit alebo je v buducnosti. Napiste dnesny cas vo formate HH:MM, napriklad: 7:10.'
        )
        return
    await _preview_open_candidate(message, state, config, candidate)


@router.message(WorkTimeStates.waiting_close_input)
async def work_time_close_input(message: Message, state: FSMContext, config: Config) -> None:
    await _start_or_continue_close(message, state, config, text=message.text or '', continuation=True)


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
        await _repeat_pending_manual_preview(message, state, config)
        return
    telegram_id = _telegram_id(message)
    candidate = _candidate_from_state((await state.get_data()).get('work_time_manual_candidate'))
    if telegram_id is None or candidate is None:
        await state.clear()
        await message.answer('Nahlad uz nie je dostupny. Skuste rozsah zadat znova.')
        return
    service = (await _require_work_time_service(message, state, config))
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
    await _answer_work_time_result(message, result, success_prefix='Pracovny cas je ulozeny.', config=config)


@router.message(WorkTimeStates.waiting_open_preview_confirm)
async def work_time_open_preview_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_approve_edit_cancel(
        context_name='work_time_open_preview',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if (await state.get_data()).get(_BOUNDARY_CHANGE_KEY) is not None:
        await _handle_boundary_decision(message, state, config, decision, field='start_time')
        return
    if decision == 'edit':
        await state.set_state(WorkTimeStates.waiting_open_input)
        await message.answer('Napiste opraveny cas prichodu, napriklad: 7:10.')
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Otvorenie pracovneho dna som zrusil. Nic sa nezmenilo.')
        return
    if decision != 'approve':
        await _repeat_pending_open_preview(message, state)
        return
    telegram_id = _telegram_id(message)
    candidate = _candidate_from_state((await state.get_data()).get('work_time_open_candidate'))
    if telegram_id is None or candidate is None or not _is_valid_explicit_open_candidate(candidate):
        await state.clear()
        await message.answer('Nahlad otvorenia uz nie je dostupny alebo cas uz nie je platny. Skuste poziadavku zadat znova.')
        return
    result = (await _require_work_time_service(message, state, config)).open_day(
        telegram_id=telegram_id,
        start_datetime=datetime.combine(candidate.work_date, candidate.start_time),
        source_message_id=getattr(message, 'message_id', None),
        expected_no_day=True,
    )
    await state.clear()
    await _answer_work_time_result(message, result, success_prefix='Pracovny den je otvoreny.', config=config)


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
    if (await state.get_data()).get(_BOUNDARY_CHANGE_KEY) is not None:
        await _handle_boundary_decision(message, state, config, decision, field='end_time')
        return
    if decision == 'edit':
        await state.set_state(WorkTimeStates.waiting_close_input)
        await message.answer('Napiste opraveny cas odchodu alebo trvanie, napriklad: o 17:00 alebo 10 hodin.')
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Uzavretie pracovneho dna som zrusil. Nic sa nezmenilo.')
        return
    if decision != 'approve':
        await _repeat_pending_close_preview(message, state, config)
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
    result = (await _require_work_time_service(message, state, config)).close_open_day(
        telegram_id=telegram_id,
        end_datetime=end_dt,
        duration_minutes=duration,
        source_message_id=getattr(message, 'message_id', None),
    )
    await state.clear()
    await _answer_work_time_result(message, result, success_prefix='Pracovny den je uzavrety.', config=config)


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
        result = (await _require_work_time_service(message, state, config)).skip_open_day(
            telegram_id=telegram_id,
            source_message_id=getattr(message, 'message_id', None),
        )
        await state.clear()
        await _answer_work_time_result(message, result, success_prefix='Otvoreny den je preskoceny.', config=config)
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


def _parse_report_period_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.isdigit():
            return int(cleaned)
    return None


def _resolve_report_period_slot(report_period: dict[str, object]) -> tuple[int, int] | None:
    current = work_time_local_date()
    month = _parse_report_period_int(report_period.get('month'))
    year = _parse_report_period_int(report_period.get('year'))
    if month is None:
        month = current.month
    if year is None:
        year = current.year
    if month < 1 or month > 12:
        return None
    if year < 1900 or year > 2100:
        return None
    return year, month

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
        f'{preview}\nZmena obvyklého nastavenia prepočíta aj staršie intervalové dni bez vlastnej prestávky. Jednodňové výnimky zostanú zachované.\n\nSchvalit, upravit alebo zrusit?',
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
        await message.answer('Povodna poziadavka na vykaz uz nie je dostupna. Skuste vykaz zadat znova.', reply_markup=ReplyKeyboardRemove())
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
    service = await _require_work_time_service(message, state, config)
    storage_key = await _work_time_report_storage_key(message, state, config)
    result = service.generate_monthly_report(
        telegram_id=telegram_id,
        year=year,
        month=month,
        output_dir=config.storage_dir / 'work_time_reports' / storage_key,
    )
    await state.clear()
    if not result.ok or result.report_path is None:
        await message.answer('Vykaz sa nepodarilo vytvorit.', reply_markup=ReplyKeyboardRemove())
        return
    await message.answer_document(
        FSInputFile(result.report_path, filename=result.report_path.name),
        caption='Vytvoril som mesacny vykaz odpracovanych hodin. Nie je to oficialny mzdovy ani pravny HR doklad.',
        reply_markup=ReplyKeyboardRemove(),
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
    summary = (await _require_work_time_service(message, state, config)).summarize_month(telegram_id=telegram_id, year=year, month=month)
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
    llm_candidate = await resolve_work_time_entry_candidate(
        user_input_text=text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        operation='manual',
    )
    if llm_candidate is not None:
        return llm_candidate
    return parse_manual_range_candidate(text) or parse_duration_entry_candidate(text)


async def _resolve_close_candidate(text: str, config: Config, open_day) -> WorkTimeCandidate | None:
    llm_candidate = await resolve_work_time_entry_candidate(
        user_input_text=text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        open_day=open_day,
        operation='close',
        allow_boundary_correction=True,
    )
    if llm_candidate is not None:
        return llm_candidate
    if config.openai_api_key and not re.fullmatch(r'\s*\d{1,2}:\d{2}\s*', text):
        return None
    if re.search(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\.\d{1,2}', text):
        return None
    return parse_close_candidate(text, open_day=open_day) if open_day is not None else None


async def _resolve_open_candidate(text: str, config: Config, *, bound_day: WorkTimeDay | None = None) -> WorkTimeCandidate | None:
    llm_candidate = await resolve_work_time_entry_candidate(
        user_input_text=text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        operation='open',
        open_day=bound_day,
        allow_boundary_correction=True,
    )
    if llm_candidate is not None:
        return llm_candidate
    if config.openai_api_key and not re.fullmatch(r'\s*\d{1,2}[:.]\d{2}\s*', text):
        return None
    if re.search(r'\b\d{4}-\d{2}-\d{2}\b', text):
        return None
    from datetime import date
    return parse_open_start_candidate(text, today=date.fromisoformat(bound_day.work_date) if bound_day else None)


def _contains_clock_like_value(text: str) -> bool:
    return re.search(r'\b\d{1,2}(?::|\.)\d{1,2}\b', text or '') is not None


def _is_valid_explicit_open_candidate(candidate: WorkTimeCandidate) -> bool:
    if candidate.close_mode != 'open_at_time' or candidate.start_time is None:
        return False
    current = work_time_local_now()
    start = datetime.combine(candidate.work_date, candidate.start_time)
    return candidate.work_date <= current.date() and start <= current


async def _effective_lunch_break_minutes_for_user(
    message: Message,
    state: FSMContext,
    config: Config,
    telegram_id: int | None,
) -> int:
    if telegram_id is None:
        return 0
    settings = (await _require_work_time_service(message, state, config)).get_lunch_break_settings(telegram_id=telegram_id)
    if not settings.configured or not settings.enabled:
        return 0
    return settings.minutes

def _should_try_llm_work_time_slots(text: str) -> bool:
    lowered = (text or '').casefold()
    if any(term in lowered for term in ('teraz', 'now')):
        return False
    return len(lowered.split()) > 2


async def _preview_manual_candidate(message: Message, state: FSMContext, config: Config, candidate: WorkTimeCandidate) -> None:
    await state.update_data(work_time_manual_candidate=_candidate_to_state(candidate))
    await state.set_state(WorkTimeStates.waiting_manual_range_confirm)
    await _send_manual_candidate_preview(
        message,
        state,
        config,
        candidate,
        prefix='Skontrolujte doplnenie pracovneho casu:',
    )


def _boundary_change_from_state(value: object) -> WorkTimeBoundaryChange | None:
    if not isinstance(value, dict):
        return None
    try:
        if type(value['revision']) is not int:
            return None
        return WorkTimeBoundaryChange(
            original=WorkTimeDay(**value['original']), proposed=WorkTimeDay(**value['proposed']),
            settings=WorkTimeLunchBreakSettings(**value['settings']), revision=value['revision'],
            field=value['field'], value=value['value'],
        )
    except (KeyError, TypeError, ValueError):
        return None


def _boundary_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[
        KeyboardButton(text='Schváliť'), KeyboardButton(text='Upraviť'), KeyboardButton(text='Zrušiť'),
    ]], resize_keyboard=True)


async def _preview_boundary_change(message, state, config, candidate, *, field: str) -> None:
    service = await _require_work_time_service(message, state, config)
    clock = candidate.start_time if field == 'start_time' else candidate.end_time
    change = service.prepare_boundary_change(
        telegram_id=_telegram_id(message), work_date=candidate.work_date.isoformat(),
        field=field, value=clock.strftime('%H:%M') if clock else '',
    )
    input_state = WorkTimeStates.waiting_open_input if field == 'start_time' else WorkTimeStates.waiting_close_input
    if change is None:
        await state.update_data(**{
            'work_time_open_target_date' if field == 'start_time' else 'work_time_close_target_date': candidate.work_date.isoformat(),
        })
        await state.set_state(input_state)
        await message.answer(
            'Zmenu casu sa nepodarilo overit. Den musi mat ulozeny prichod, '
            'odchod nesmie byt skor ako prichod a cas nesmie byt v buducnosti. '
            'Zadajte opraveny cas alebo zruste krok.', reply_markup=ReplyKeyboardRemove(),
        )
        return
    before = change.original
    after = change.proposed
    preview_candidate = WorkTimeCandidate(
        work_date=candidate.work_date, start_time=_parse_hhmm(after.start_time),
        end_time=_parse_hhmm(after.end_time) if after.end_time else None,
    )
    lunch = (before.lunch_break_minutes_override if before.lunch_break_minutes_override is not None
             else change.settings.minutes if change.settings.configured and change.settings.enabled else 0)
    preview = (
        'Skontrolujte zmenu ulozeneho pracovneho casu:\n'
        f'Povodne: {before.start_time or "-"} - {before.end_time or "-"}\n'
        f'{format_candidate_preview(preview_candidate, lunch_break_minutes=lunch)}\n'
        f'Obedna prestavka: {lunch} minut. Druhy cas zostane zachovany.\n'
    )
    if before.net_work_minutes_override is not None and before.lunch_break_minutes_override is None:
        preview += 'Povodny pevny pocet hodin nahradi vypocet z potvrdeneho rozsahu.\n'
    preview += '\nSchvalit, upravit alebo zrusit?'
    await state.update_data(**{
        _BOUNDARY_CHANGE_KEY: asdict(change), 'work_time_boundary_preview': preview,
        'work_time_close_target_date': before.work_date,
    })
    await state.set_state(
        WorkTimeStates.waiting_open_preview_confirm if field == 'start_time'
        else WorkTimeStates.waiting_close_preview_confirm
    )
    await message.answer(preview, reply_markup=_boundary_keyboard())


async def _repeat_boundary_preview(message, state) -> None:
    data = await state.get_data()
    change = _boundary_change_from_state(data.get(_BOUNDARY_CHANGE_KEY))
    preview = data.get('work_time_boundary_preview')
    if change is None or not isinstance(preview, str):
        await state.clear()
        await message.answer('Nahlad opravy uz nie je dostupny. Zadajte poziadavku znova.', reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(preview, reply_markup=_boundary_keyboard())


async def _handle_boundary_decision(message, state, config, decision: str, *, field: str) -> None:
    if decision == 'edit':
        await state.set_state(WorkTimeStates.waiting_open_input if field == 'start_time' else WorkTimeStates.waiting_close_input)
        await message.answer('Napiste opraveny presny cas vo formate HH:MM.', reply_markup=ReplyKeyboardRemove())
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Opravu casu som zrusil. Nic sa nezmenilo.', reply_markup=ReplyKeyboardRemove())
        return
    if decision != 'approve':
        await _repeat_boundary_preview(message, state)
        return
    change = _boundary_change_from_state((await state.get_data()).get(_BOUNDARY_CHANGE_KEY))
    if change is None or change.field != field or change.original.telegram_id != _telegram_id(message):
        await state.clear()
        await message.answer('Nahlad opravy uz nie je platny. Zadajte poziadavku znova.', reply_markup=ReplyKeyboardRemove())
        return
    try:
        service = await _require_work_time_service(message, state, config)
        result = service.apply_boundary_change(
            telegram_id=_telegram_id(message), change=change,
            source_message_id=getattr(message, 'message_id', None),
        )
    except (sqlite3.Error, RuntimeError):
        _LOG.exception('Work-time boundary correction failed')
        await state.clear()
        await message.answer('Opravu sa nepodarilo bezpecne ulozit. Skontrolujte zaznam a skuste znova.', reply_markup=ReplyKeyboardRemove())
        return
    await state.clear()
    if result.ok and result.day is not None and result.day.status == 'closed':
        await send_closed_day_summary(message, config, result.day, service=service, prefix='Potvrdený pracovný čas je uložený.')
        return
    text = (
        ('Cas uz zodpoveda zadaniu.' if result.reason == 'unchanged' else 'Potvrdeny pracovny cas je ulozeny.')
        + '\n' + format_day_summary(result.day)
        if result.ok and result.day is not None
        else 'Zaznam, nastavenia alebo platnost casu sa zmenili. Nic som neprepisal. Zadajte novy nahlad.'
    )
    try:
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
    except Exception:
        # Do not reverse or repeat a committed business effect on Telegram failure.
        _LOG.exception('Work-time correction result/keyboard delivery failed')


async def _preview_open_candidate(message: Message, state: FSMContext, config: Config, candidate: WorkTimeCandidate) -> None:
    service = await _require_work_time_service(message, state, config)
    existing = service.get_day(telegram_id=_telegram_id(message), work_date=candidate.work_date.isoformat())
    if existing is not None:
        await _preview_boundary_change(message, state, config, candidate, field='start_time')
        return
    if candidate.work_date != work_time_local_date():
        await state.set_state(WorkTimeStates.waiting_open_input)
        await message.answer('Pre tento datum nie je ulozeny den na opravu. Napiste dnesny prichod alebo zruste krok.')
        return
    await state.update_data(work_time_open_candidate=_candidate_to_state(candidate), **{_BOUNDARY_CHANGE_KEY: None})
    await state.set_state(WorkTimeStates.waiting_open_preview_confirm)
    await answer_with_decision_keyboard(
        message,
        'Skontrolujte otvorenie pracovneho dna:\n'
        f'{format_candidate_preview(candidate)}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


async def _repeat_pending_open_preview(message: Message, state: FSMContext) -> None:
    if (await state.get_data()).get(_BOUNDARY_CHANGE_KEY) is not None:
        await _repeat_boundary_preview(message, state)
        return
    candidate = _candidate_from_state((await state.get_data()).get('work_time_open_candidate'))
    if candidate is None:
        await state.clear()
        await message.answer('Nahlad otvorenia uz nie je dostupny. Skuste poziadavku zadat znova.')
        return
    await answer_with_decision_keyboard(
        message,
        'Mate rozpracovany nahlad otvorenia pracovneho dna. Najprv ho schvalte, upravte alebo zruste.\n'
        f'{format_candidate_preview(candidate)}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


async def _preview_close_candidate(
    message: Message,
    state: FSMContext,
    config: Config,
    candidate: WorkTimeCandidate,
    open_day: WorkTimeDay,
) -> None:
    if candidate.close_mode == 'close_at_time':
        await _preview_boundary_change(message, state, config, candidate, field='end_time')
        return
    telegram_id = _telegram_id(message)
    await state.update_data(
        **{_BOUNDARY_CHANGE_KEY: None},
        work_time_close_candidate=_candidate_to_state(candidate),
        work_time_close_open_day_id=open_day.id,
    )
    await state.set_state(WorkTimeStates.waiting_close_preview_confirm)
    await answer_with_decision_keyboard(
        message,
        'Skontrolujte uzavretie pracovneho dna:\n'
        f'{format_candidate_preview(candidate, open_day=open_day, lunch_break_minutes=await _effective_lunch_break_minutes_for_user(message, state, config, telegram_id))}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


async def _send_manual_candidate_preview(
    message: Message,
    state: FSMContext,
    config: Config,
    candidate: WorkTimeCandidate,
    *,
    prefix: str,
) -> None:
    await answer_with_decision_keyboard(
        message,
        f'{prefix}\n'
        f'{format_candidate_preview(candidate, lunch_break_minutes=await _effective_lunch_break_minutes_for_user(message, state, config, _telegram_id(message)))}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


async def _repeat_pending_manual_preview(message: Message, state: FSMContext, config: Config) -> None:
    candidate = _candidate_from_state((await state.get_data()).get('work_time_manual_candidate'))
    if candidate is None:
        await state.clear()
        await message.answer('Nahlad uz nie je dostupny. Skuste rozsah zadat znova.')
        return
    await _send_manual_candidate_preview(
        message,
        state,
        config,
        candidate,
        prefix='Mate rozpracovany nahlad doplnenia pracovneho casu. Najprv ho schvalte, upravte alebo zruste.',
    )


async def _repeat_pending_close_preview(message: Message, state: FSMContext, config: Config) -> None:
    if (await state.get_data()).get(_BOUNDARY_CHANGE_KEY) is not None:
        await _repeat_boundary_preview(message, state)
        return
    data = await state.get_data()
    candidate = _candidate_from_state(data.get('work_time_close_candidate'))
    telegram_id = _telegram_id(message)
    open_day = None
    try:
        open_day_id = int(data.get('work_time_close_open_day_id'))
    except (TypeError, ValueError):
        open_day_id = None
    if telegram_id is not None and open_day_id is not None:
        open_day = (await _require_work_time_service(message, state, config)).get_day_by_id(open_day_id)
        if open_day is not None and open_day.telegram_id != telegram_id:
            open_day = None
    if candidate is None or open_day is None:
        await state.clear()
        await message.answer('Nahlad uz nie je dostupny. Skuste uzavretie zadat znova.')
        return
    await answer_with_decision_keyboard(
        message,
        'Mate rozpracovany nahlad doplnenia pracovneho casu. Najprv ho schvalte, upravte alebo zruste.\n'
        f'{format_candidate_preview(candidate, open_day=open_day, lunch_break_minutes=await _effective_lunch_break_minutes_for_user(message, state, config, telegram_id))}\n\n'
        'Schvalit, upravit alebo zrusit?',
        approve_edit_cancel_keyboard(),
    )


async def _answer_work_time_result(message: Message, result, *, success_prefix: str, config: Config | None = None) -> None:
    if result.ok and result.day is not None:
        if config is not None and result.day.status == 'closed':
            await send_closed_day_summary(message, config, result.day, prefix=success_prefix)
            return
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
    if result.reason == 'day_changed':
        await message.answer('Zaznam sa medzicasom zmenil. Nic som neprepisal. Zadajte novy nahlad.', reply_markup=ReplyKeyboardRemove())
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
