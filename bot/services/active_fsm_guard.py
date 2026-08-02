from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Config
from bot.services.active_fsm_state_descriptors import (
    ActiveFsmStateDescriptor,
    describe_active_fsm_state,
    render_active_fsm_help,
)
from bot.services.decision_resolver import (
    resolve_active_fsm_navigation,
    resolve_approve_edit_cancel,
    resolve_yes_no,
)
from bot.services.semantic_action_resolver import resolve_semantic_action


ACTIVE_FSM_STARTED_AT_KEY = 'active_fsm_started_at'
ACTIVE_FSM_LAST_ACTIVITY_AT_KEY = 'active_fsm_last_activity_at'
ACTIVE_FSM_STATE_KEY = 'active_fsm_state'

ACTIVE_FSM_STALE_MESSAGE = (
    'Mali ste rozpracovanú akciu. Ukončil som ju, aby sme mohli pokračovať.'
)
ACTIVE_FSM_EXPIRED_MESSAGE = (
    'Predchádzajúca rozpracovaná akcia vypršala. Začnite ju prosím znova.'
)

_DATA_ENTRY_TIMEOUT_SECONDS = 30 * 60
_CONFIRMATION_TIMEOUT_SECONDS = 15 * 60
_DESTRUCTIVE_TIMEOUT_SECONDS = 10 * 60
_EXACT_DESTRUCTIVE_TIMEOUT_SECONDS = 5 * 60

_UNKNOWN_TOP_LEVEL_ACTION = 'unknown'
_TOP_LEVEL_PROBE_ACTIONS = [
    'start',
    'create_invoice',
    'show_existing_invoice',
    'invoice_analytics',
    'accounting_document_analytics',
    'show_supplier_profile',
    'edit_supplier',
    'add_contact',
    'add_service_alias',
    'show_recent_accounting_documents',
    'add_receipt',
    'delete_user_database',
    'open_work_day',
    'close_work_day',
    'add_work_time_entry',
    'generate_work_time_report',
    'delete_work_time_month',
    'update_work_time_lunch_break',
    'send_invoice',
    'edit_existing_invoice',
    'delete_existing_invoice',
    'mark_existing_invoice_paid',
    'edit_invoice',
    _UNKNOWN_TOP_LEVEL_ACTION,
]

_MUTATING_REPLY_EXACT_TEXT = {
    'ulozit',
    'save',
    'odoslat',
    'send',
    'zaplatit',
    'uhradit',
    'mark paid',
    'oznacit ako zaplatenu',
    'vymazat',
    'delete',
}

_KNOWN_COMMANDS = {
    '/start', '/menu', '/cancel', '/issue', '/invoice', '/moj_profil',
    '/upravit_profil', '/onboarding', '/supplier', '/service', '/alias',
    '/sluzbu', '/contact', '/contact_add', '/add_kontakt', '/doklad',
    '/expense', '/intake', '/add_blocek', '/dodat_blocek', '/blocky',
    '/blocek', '/profily', '/dochadzka', '/vymazat_databazu',
    '/access_requests', '/customization_requests', '/customization_request',
    '/customization_request_accept', '/customization_request_reject',
    '/customization_request_reply', '/approve', '/reject', '/block', '/users',
    '/gmail_connect', '/gmail_status', '/gmail_disconnect',
    '/google_drive_connect', '/google_drive_status', '/google_drive_disconnect',
}

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActiveFsmAge:
    current_state: str
    last_activity_at: datetime | None
    timeout_seconds: int
    is_stale: bool
    is_legacy_unknown_age: bool


class ActiveFsmMessageMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        state = data.get('state')
        config = data.get('config')
        if not isinstance(config, Config) or state is None or not hasattr(state, 'get_state'):
            return await handler(event, data)

        current_state = await state.get_state()
        if current_state is None:
            result = await handler(event, data)
            await touch_active_fsm_activity(state)
            return result

        text = (getattr(event, 'text', None) or '').strip()
        if text:
            event_update = data.get('event_update')
            handled = await handle_active_fsm_text_update(
                message=event,
                state=state,
                config=config,
                text=text,
                input_channel='command' if text.startswith('/') else 'text',
                telegram_update_id=getattr(event_update, 'update_id', None),
            )
            if handled:
                return None

        result = await handler(event, data)
        await touch_active_fsm_activity(state)
        return result


async def handle_active_fsm_text_update(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    text: str,
    input_channel: str,
    request_id: str | None = None,
    telegram_update_id: int | None = None,
) -> bool:
    current_state = await state.get_state()
    if current_state is None:
        return False

    age = await get_active_fsm_age(state=state, current_state=current_state)
    command = _command_token(text)
    actor_id = getattr(getattr(message, 'from_user', None), 'id', None)
    from bot.handlers.runtime_issue import (
        RUNTIME_ISSUE_FAILURE,
        RUNTIME_ISSUE_USAGE,
        RuntimeIssueAdminCheck,
        check_runtime_issue_admin,
        extract_runtime_issue_command,
        extract_runtime_issue_prefix_description,
        handle_runtime_issue_capture,
    )

    runtime_issue_admin_check = check_runtime_issue_admin(config, actor_id)
    runtime_issue_admin = runtime_issue_admin_check == RuntimeIssueAdminCheck.ADMIN
    issue_command_description = extract_runtime_issue_command(text)
    if issue_command_description is not None:
        if runtime_issue_admin_check == RuntimeIssueAdminCheck.FAILED:
            await message.answer(RUNTIME_ISSUE_FAILURE)
            return True
        if runtime_issue_admin:
            if not issue_command_description:
                from bot.handlers.runtime_issue import RUNTIME_ISSUE_USAGE

                await message.answer(RUNTIME_ISSUE_USAGE)
                return True
            return await handle_runtime_issue_capture(
                message=message,
                state=state,
                config=config,
                description=issue_command_description,
                source_channel=input_channel,
                telegram_update_id=telegram_update_id,
            )

    issue_prefix_description = extract_runtime_issue_prefix_description(text)
    if runtime_issue_admin and issue_prefix_description is not None:
        if not issue_prefix_description:
            await message.answer(RUNTIME_ISSUE_USAGE)
            return True
        return await handle_runtime_issue_capture(
            message=message,
            state=state,
            config=config,
            description=text,
            source_channel=input_channel,
            telegram_update_id=telegram_update_id,
        )

    if command in {'/cancel', '/menu', '/start'}:
        await _execute_navigation(
            decision={
                '/cancel': 'cancel_current_flow',
                '/menu': 'show_main_menu',
                '/start': 'resume_start_status',
            }[command],
            message=message,
            state=state,
            config=config,
        )
        return True

    if runtime_issue_admin:
        from bot.handlers.runtime_issue import (
            handle_runtime_issue_capture,
            resolve_runtime_issue_intent,
        )

        try:
            is_runtime_issue = await resolve_runtime_issue_intent(
                text=text,
                config=config,
                current_state=current_state,
                input_channel=input_channel,
            )
        except Exception:
            logger.exception('Runtime issue intent resolver failed')
            is_runtime_issue = False
        if is_runtime_issue:
            return await handle_runtime_issue_capture(
                message=message,
                state=state,
                config=config,
                description=text,
                source_channel=input_channel,
                telegram_update_id=telegram_update_id,
            )

    if command and command in _KNOWN_COMMANDS:
        return False
    navigation_decision = 'contextual_recovery' if command else (
        await _resolve_navigation_for_update(
            text=text,
            current_state=current_state,
            config=config,
            input_channel=input_channel,
            request_id=request_id,
        )
    )
    if navigation_decision in {'cancel_current_flow', 'show_main_menu', 'resume_start_status'}:
        await _execute_navigation(
            decision=navigation_decision,
            message=message,
            state=state,
            config=config,
        )
        return True

    state_data = await state.get_data()
    if _has_intake_session_expiry(state_data) and (age.is_legacy_unknown_age or age.is_stale):
        return False

    if age.is_stale:
        if await is_stale_mutating_reply_text(text):
            await expire_active_fsm_state(message=message, state=state, config=config)
            return True
        await clear_current_state_safely(state=state, config=config)
        await message.answer(ACTIVE_FSM_STALE_MESSAGE)
        from bot.services.conversation_context import clear_conversation_for_message
        clear_conversation_for_message(message)
        await _route_through_idle_top_level(
            message=message,
            state=state,
            config=config,
            text=text,
            input_channel=input_channel,
            request_id=request_id,
        )
        await touch_active_fsm_activity(state)
        return True

    if age.is_legacy_unknown_age:
        if await is_stale_mutating_reply_text(text):
            await expire_active_fsm_state(message=message, state=state, config=config)
            return True
        if await _looks_like_top_level_request(text=text, config=config, current_state=current_state):
            await clear_current_state_safely(state=state, config=config)
            await message.answer(ACTIVE_FSM_STALE_MESSAGE)
            from bot.services.conversation_context import clear_conversation_for_message
            clear_conversation_for_message(message)
            await _route_through_idle_top_level(
                message=message,
                state=state,
                config=config,
                text=text,
                input_channel=input_channel,
                request_id=request_id,
            )
            await touch_active_fsm_activity(state)
            return True

    if navigation_decision in {'describe_active_flow', 'describe_expected_input'}:
        help_text, keyboard = render_active_fsm_help(
            current_state,
            expected_only=navigation_decision == 'describe_expected_input',
        )
        await message.answer(help_text, reply_markup=keyboard)
        await touch_active_fsm_activity(state)
        return True

    if navigation_decision == 'contextual_recovery':
        await handle_contextual_info_help_recovery(
            message=message,
            state=state,
            config=config,
            text=text,
            input_channel=input_channel,
            active_state_descriptor=describe_active_fsm_state(current_state),
        )
        await touch_active_fsm_activity(state)
        return True

    return False


async def get_active_fsm_age(*, state: FSMContext, current_state: str | None = None) -> ActiveFsmAge:
    resolved_state = current_state or await state.get_state()
    if resolved_state is None:
        raise ValueError('active_fsm_age_requires_state')
    data = await state.get_data()
    last_activity_at = _parse_timestamp(data.get(ACTIVE_FSM_LAST_ACTIVITY_AT_KEY))
    timeout_seconds = active_fsm_timeout_seconds(resolved_state)
    is_legacy = last_activity_at is None
    is_stale = bool(last_activity_at and _utc_now() - last_activity_at >= timedelta(seconds=timeout_seconds))
    return ActiveFsmAge(
        current_state=resolved_state,
        last_activity_at=last_activity_at,
        timeout_seconds=timeout_seconds,
        is_stale=is_stale,
        is_legacy_unknown_age=is_legacy,
    )


async def touch_active_fsm_activity(state: FSMContext, *, now: datetime | None = None) -> None:
    if state is None or not hasattr(state, 'get_state') or not hasattr(state, 'update_data'):
        return
    current_state = await state.get_state()
    if current_state is None:
        return
    timestamp = _format_timestamp(_utc_now(now))
    data = await state.get_data()
    updates: dict[str, object] = {
        ACTIVE_FSM_LAST_ACTIVITY_AT_KEY: timestamp,
        ACTIVE_FSM_STATE_KEY: current_state,
    }
    if not data.get(ACTIVE_FSM_STARTED_AT_KEY):
        updates[ACTIVE_FSM_STARTED_AT_KEY] = timestamp
    await state.update_data(**updates)


async def expire_active_fsm_state(*, message: Message, state: FSMContext, config: Config) -> None:
    await clear_current_state_safely(state=state, config=config)
    await message.answer(ACTIVE_FSM_EXPIRED_MESSAGE)
    from bot.services.conversation_context import clear_conversation_for_message
    clear_conversation_for_message(message)


async def clear_current_state_safely(*, state: FSMContext, config: Config) -> None:
    from bot.handlers.state_control import clear_current_state_safely as _clear_current_state_safely

    await _clear_current_state_safely(state=state, config=config)


async def is_active_fsm_callback_stale_or_legacy(
    *,
    state: FSMContext,
    current_state: str | None,
) -> bool:
    if current_state is None:
        return True
    age = await get_active_fsm_age(state=state, current_state=current_state)
    return age.is_stale or age.is_legacy_unknown_age


async def is_stale_mutating_reply_text(text: str) -> bool:
    normalized = _normalize_text(text)
    if normalized in {_normalize_text(value) for value in _MUTATING_REPLY_EXACT_TEXT}:
        return True
    approve_edit_cancel = await resolve_approve_edit_cancel(
        context_name='invoice_preview_confirmation',
        user_input_text=text,
        api_key=None,
        model='gpt-4o',
    )
    if approve_edit_cancel in {'approve', 'edit'}:
        return True
    yes_no = await resolve_yes_no(
        context_name='contact_confirm',
        user_input_text=text,
        api_key=None,
        model='gpt-4o',
    )
    return yes_no in {'yes', 'no'}


def active_fsm_timeout_seconds(current_state: str) -> int:
    normalized = current_state.casefold()
    if 'deleteuserdatabasestates:waiting_exact_confirmation' in normalized:
        return _EXACT_DESTRUCTIVE_TIMEOUT_SECONDS
    if any(token in normalized for token in ('delete', 'mark_existing_invoice_paid')):
        return _DESTRUCTIVE_TIMEOUT_SECONDS
    if any(token in normalized for token in ('confirm', 'decision', 'preview', 'choice', 'duplicate')):
        return _CONFIRMATION_TIMEOUT_SECONDS
    return _DATA_ENTRY_TIMEOUT_SECONDS


async def _resolve_navigation_for_update(
    *,
    text: str,
    current_state: str,
    config: Config,
    input_channel: str,
    request_id: str | None,
) -> str:
    try:
        return await resolve_active_fsm_navigation(
            context_name='active_fsm_navigation',
            user_input_text=text,
            current_state=current_state,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
            diagnostics={'input_channel': input_channel, 'request_id': request_id},
        )
    except Exception:
        logger.exception('Active FSM navigation resolver failed')
        return 'pass_through'


async def _execute_navigation(*, decision: str, message: Message, state: FSMContext, config: Config) -> None:
    if decision == 'cancel_current_flow':
        from bot.handlers.state_control import cancel_current_state

        await cancel_current_state(message=message, state=state, config=config)
        return

    await clear_current_state_safely(state=state, config=config)
    if decision == 'show_main_menu':
        from bot.handlers.start import cmd_menu

        await cmd_menu(message=message, config=config, state=state)
        return
    if decision == 'resume_start_status':
        from bot.handlers.start import cmd_start

        await cmd_start(message=message, config=config, state=state)
        return


async def _route_through_idle_top_level(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    text: str,
    input_channel: str,
    request_id: str | None,
) -> None:
    from bot.handlers.invoice import process_invoice_text

    await process_invoice_text(
        message=message,
        state=state,
        config=config,
        invoice_text=text,
        request_id=request_id,
        input_channel=input_channel,
    )


async def handle_contextual_info_help_recovery(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    text: str,
    input_channel: str,
    active_state_descriptor: ActiveFsmStateDescriptor,
) -> None:
    from bot.services.contextual_info_help_recovery import (
        action_label,
        default_recovery_action_ids,
        default_recovery_capability_ids,
        resolve_contextual_recovery,
    )
    from bot.services.conversation_context import (
        conversation_context_service,
        current_active_conversation_turn,
    )

    actor_id = int(getattr(getattr(message, 'from_user', None), 'id', 0))
    chat_id = int(getattr(getattr(message, 'chat', None), 'id', 0))
    active_turn = current_active_conversation_turn()
    workspace_id = active_turn.workspace_id if active_turn is not None else None
    recent_turns = [
        turn.to_prompt_dict()
        for turn in conversation_context_service.recent_turns(actor_id, chat_id, workspace_id)
    ] if actor_id and chat_id else []
    result = await resolve_contextual_recovery(
        user_input=text,
        input_channel=input_channel,
        recent_turns=recent_turns,
        active_state_descriptor=active_state_descriptor,
        action_ids=default_recovery_action_ids(),
        capability_ids=default_recovery_capability_ids(),
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    help_text, keyboard = render_active_fsm_help(
        active_state_descriptor.state_name or '',
        expected_only=result.outcome == 'describe_expected_input',
    )
    if result.outcome == 'genuinely_unclear':
        help_text = 'Tejto odpovedi som nerozumel.\n' + help_text
    elif result.outcome not in {'describe_active_flow', 'describe_expected_input'}:
        alternative = result.action_id or (
            result.candidate_action_ids[0] if result.candidate_action_ids else None
        )
        if alternative:
            help_text = f'Vyzerá to však, že sa pýtate na: {action_label(alternative)}.\n' + help_text
        else:
            help_text = 'Táto správa nezodpovedá očakávanému vstupu aktuálneho kroku.\n' + help_text
    await message.answer(help_text, reply_markup=keyboard)


async def _looks_like_top_level_request(*, text: str, config: Config, current_state: str) -> bool:
    try:
        decision = await resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=_TOP_LEVEL_PROBE_ACTIONS,
            user_input_text=text,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
            auxiliary_context={
                'current_state': current_state,
                'probe_only': True,
                'no_side_effects': True,
            },
        )
    except Exception:
        logger.exception('Top-level stale-state probe failed')
        return False
    return decision != _UNKNOWN_TOP_LEVEL_ACTION


def _has_intake_session_expiry(data: dict[str, Any]) -> bool:
    return isinstance(data.get('intake_expires_at'), str)


def _command_token(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith('/'):
        return ''
    return stripped.split(maxsplit=1)[0].split('@', 1)[0].lower()


def _normalize_text(value: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize('NFKD', value.strip().casefold())
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_diacritics).strip()


def _utc_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return _utc_now(parsed)
