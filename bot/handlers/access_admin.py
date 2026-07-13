from __future__ import annotations

from datetime import UTC, datetime
import logging
import re
import unicodedata
from uuid import uuid4

from aiogram import Bot
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import Message

from bot.config import Config
from bot.keyboards.decision import answer_with_decision_keyboard, approve_edit_cancel_keyboard
from bot.handlers.start import APPROVED_ACCESS_NEXT_STEP_MESSAGE
from bot.services.access_control import (
    ACCESS_STATUS_PENDING,
    AccessApprovalWorkspaceConflict,
    AccessControlService,
)
from bot.services.authorization import UNAUTHORIZED_MESSAGE, is_admin_telegram_user
from bot.services.customization_requests import (
    RESPONSE_DELIVERY_FAILED,
    RESPONSE_DELIVERY_PENDING,
    RESPONSE_DELIVERY_SUCCEEDED,
    RESPONSE_KIND_ANSWER,
    RESPONSE_RESULT_ALREADY_FAILED,
    RESPONSE_RESULT_ALREADY_IN_PROGRESS,
    RESPONSE_RESULT_ALREADY_SENT,
    RESPONSE_RESULT_CLAIMED_FOR_SEND,
    RESPONSE_RESULT_NOT_FOUND,
    RESPONSE_RESULT_PREPARED,
    REVIEW_RESULT_ALREADY_PROCESSED,
    REVIEW_RESULT_NOT_FOUND,
    REVIEW_RESULT_UPDATED,
    STATUS_REVIEWED_ACCEPTED,
    STATUS_REVIEWED_REJECTED,
    CustomizationRequestRecord,
    CustomizationRequestService,
    redact_customization_request_text,
)
from bot.services.decision_resolver import resolve_approve_edit_cancel


router = Router(name='access_admin')
logger = logging.getLogger(__name__)
_CUSTOMIZATION_REQUEST_ADMIN_LIMIT = 10
_CUSTOMIZATION_REQUEST_DETAIL_PREFIX_MIN_LENGTH = 8
_CUSTOMIZATION_REQUEST_DETAIL_MAX_MESSAGE_LENGTH = 3500
_CUSTOMIZATION_RESPONSE_PENDING_STUCK_MINUTES = 15
_CUSTOMIZATION_RESPONSE_DRAFT_KEY = 'customization_request_admin_response_draft'
_CUSTOMIZATION_RESPONSE_CONFIRM_CONTEXT = 'customization_request_admin_response_preview'
_CUSTOMIZATION_RESPONSE_MAX_LENGTH = 1500
_CUSTOMIZATION_RESPONSE_SENT_MESSAGE = 'Odpoveď bola odoslaná používateľovi.'
_CUSTOMIZATION_RESPONSE_ALREADY_SENT_MESSAGE = 'Odpoveď už bola odoslaná používateľovi. Neodoslal som ju znova.'
_CUSTOMIZATION_RESPONSE_IN_PROGRESS_MESSAGE = 'Odpoveď sa už odosiela. Neodoslal som ju znova.'
_CUSTOMIZATION_RESPONSE_ALREADY_FAILED_MESSAGE = 'Odpoveď už je uložená ako nedoručená. Automaticky ju neposielam znova.'
_CUSTOMIZATION_RESPONSE_FAILED_MESSAGE = 'Odpoveď som uložil, ale nepodarilo sa ju doručiť používateľovi.'
_CUSTOMIZATION_RESPONSE_STATUS_UPDATE_FAILED_MESSAGE = (
    'Odpoveď bola odoslaná používateľovi, ale stav doručenia sa nepodarilo uložiť.'
)


class CustomizationRequestAdminResponseStates(StatesGroup):
    waiting_response_text = State()
    waiting_response_preview_decision = State()


_ACCESS_REQUESTS_ALIASES = {
    'access requests',
    'access_requests',
    'ziadosti',
    'ziadosti o pristup',
    'zapros',
    '\u0437\u0430\u043f\u0440\u043e\u0441',
    '\u0437\u0430\u043f\u0438\u0442',
    '\u0437\u0430\u043f\u0438\u0442\u0438',
    '\u0437\u0430\u043f\u0438\u0442\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u0443',
    '\u0437\u0430\u044f\u0432\u043a\u0438',
    '\u0437\u0430\u044f\u0432\u043a\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u0443',
}

_USERS_ALIASES = {
    'users',
    'pouzivatelia',
    'pouzivatel',
    '\u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0438',
    '\u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456',
    '\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438',
}


@router.message(Command('access_requests'))
async def cmd_access_requests(message: Message, config: Config) -> None:
    await _send_access_requests(message, config)


@router.message(Command('customization_requests'))
async def cmd_customization_requests(message: Message, config: Config) -> None:
    await _send_customization_requests(message, config)


@router.message(Command('customization_request'))
async def cmd_customization_request_detail(message: Message, config: Config) -> None:
    await _send_customization_request_detail(message, config)


@router.message(Command('customization_request_accept'))
async def cmd_customization_request_accept(message: Message, config: Config) -> None:
    await _review_customization_request(message, config, decision=STATUS_REVIEWED_ACCEPTED)


@router.message(Command('customization_request_reject'))
async def cmd_customization_request_reject(message: Message, config: Config) -> None:
    await _review_customization_request(message, config, decision=STATUS_REVIEWED_REJECTED)


@router.message(Command('customization_request_reply'))
async def cmd_customization_request_reply(message: Message, config: Config, state: FSMContext) -> None:
    await _start_customization_request_reply(message=message, config=config, state=state)


@router.message(CustomizationRequestAdminResponseStates.waiting_response_text)
async def customization_request_response_text(message: Message, state: FSMContext) -> None:
    response_text = _clean_response_text(message.text or '')
    if response_text is None:
        await message.answer('Napíšte odpoveď pre používateľa textom.')
        return
    if len(response_text) > _CUSTOMIZATION_RESPONSE_MAX_LENGTH:
        await message.answer(f'Odpoveď je príliš dlhá. Skráťte ju na najviac {_CUSTOMIZATION_RESPONSE_MAX_LENGTH} znakov.')
        return

    state_data = await state.get_data()
    draft = state_data.get(_CUSTOMIZATION_RESPONSE_DRAFT_KEY)
    if not isinstance(draft, dict):
        await state.clear()
        await message.answer('Návrh odpovede už nie je dostupný. Odpoveď nebola odoslaná.')
        return

    updated_draft = dict(draft)
    updated_draft['response_text'] = response_text
    await state.update_data(**{_CUSTOMIZATION_RESPONSE_DRAFT_KEY: updated_draft})
    await state.set_state(CustomizationRequestAdminResponseStates.waiting_response_preview_decision)
    await answer_with_decision_keyboard(
        message,
        _format_customization_response_preview(updated_draft),
        approve_edit_cancel_keyboard(),
    )


@router.message(CustomizationRequestAdminResponseStates.waiting_response_preview_decision)
async def customization_request_response_preview_decision(
    message: Message,
    state: FSMContext,
    config: Config,
    bot: Bot | None = None,
    canonical_decision: str | None = None,
) -> None:
    state_data = await state.get_data()
    draft = state_data.get(_CUSTOMIZATION_RESPONSE_DRAFT_KEY)
    if not isinstance(draft, dict):
        await state.clear()
        await message.answer('Návrh odpovede už nie je dostupný. Odpoveď nebola odoslaná.')
        return

    if not _is_response_draft_owner(message, draft):
        await state.clear()
        await message.answer('Tento návrh odpovede patrí inému správcovi. Odpoveď nebola odoslaná.')
        return

    if canonical_decision is None:
        decision = await resolve_approve_edit_cancel(
            context_name=_CUSTOMIZATION_RESPONSE_CONFIRM_CONTEXT,
            user_input_text=(message.text or ''),
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    else:
        decision = canonical_decision if canonical_decision in {'approve', 'edit', 'cancel', 'unknown'} else 'unknown'

    if decision == 'unknown':
        await message.answer('Prosím, odpovedzte: odoslať, upraviť alebo zrušiť.')
        return
    if decision == 'cancel':
        await state.clear()
        await message.answer('Zrušené. Odpoveď nebola odoslaná.')
        return
    if decision == 'edit':
        await state.set_state(CustomizationRequestAdminResponseStates.waiting_response_text)
        await message.answer('Napíšte upravenú odpoveď pre používateľa textom.')
        return

    await _send_customization_request_response(
        message=message,
        state=state,
        config=config,
        draft=draft,
        bot=bot,
    )


@router.message(
    StateFilter(None),
    lambda message: _normalize_alias(message.text or '') in _ACCESS_REQUESTS_ALIASES,
)
async def access_requests_alias(message: Message, config: Config) -> None:
    await _send_access_requests(message, config)


async def _send_access_requests(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    requests = AccessControlService(config.db_path).list_access_requests(status=ACCESS_STATUS_PENDING)
    if not requests:
        await message.answer('Nie su ziadne cakajuce ziadosti o pristup.')
        return

    lines = ['Cakajuce ziadosti o pristup:']
    for request in requests:
        lines.append(
            _format_access_request_line(
                telegram_id=request.telegram_id,
                username=request.username,
                first_name=request.first_name,
                last_name=request.last_name,
                status=request.status,
            )
        )
    await message.answer('\n'.join(lines))


async def _send_customization_requests(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    requests = CustomizationRequestService(config.db_path).list_pending_customization_requests_for_admin(
        limit=_CUSTOMIZATION_REQUEST_ADMIN_LIMIT,
    )
    if not requests:
        await message.answer('Moment\u00e1lne nie s\u00fa \u017eiadne po\u017eiadavky \u010dakaj\u00face na kontrolu.')
        return

    lines = ['Po\u017eiadavky \u010dakaj\u00face na kontrolu:']
    for request in requests:
        lines.extend(_format_customization_request_lines(request))
    await message.answer('\n'.join(lines))


async def _send_customization_request_detail(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    request_id_or_prefix = _parse_text_arg(message.text or '')
    if request_id_or_prefix is None:
        await message.answer('Pou\u017eitie: /customization_request <request_id>')
        return

    service = CustomizationRequestService(config.db_path)
    lookup_result, request = _lookup_customization_request_for_admin(
        service=service,
        request_id_or_prefix=request_id_or_prefix,
    )
    if lookup_result != 'found' or request is None:
        await _answer_customization_request_lookup_failure(message, lookup_result)
        return

    await message.answer(_format_customization_request_detail(request))


async def _review_customization_request(message: Message, config: Config, *, decision: str) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    request_id_or_prefix = _parse_text_arg(message.text or '')
    if request_id_or_prefix is None:
        await message.answer(f'Pou\u017eitie: /{_review_command_name(decision)} <request_id>')
        return

    service = CustomizationRequestService(config.db_path)
    lookup_result, request = _lookup_customization_request_for_admin(
        service=service,
        request_id_or_prefix=request_id_or_prefix,
    )
    if lookup_result != 'found' or request is None:
        await _answer_customization_request_lookup_failure(message, lookup_result)
        return

    admin_telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    result, _ = service.mark_customization_request_reviewed_for_admin(
        request_id=request.request_id,
        admin_telegram_id=admin_telegram_id,
        decision=decision,
    )
    if result == REVIEW_RESULT_UPDATED and decision == STATUS_REVIEWED_ACCEPTED:
        await message.answer('Po\u017eiadavka bola ozna\u010den\u00e1 ako prijat\u00e1 na neskor\u0161iu kontrolu. Neznamen\u00e1 to automatick\u00fa implement\u00e1ciu.')
        return
    if result == REVIEW_RESULT_UPDATED and decision == STATUS_REVIEWED_REJECTED:
        await message.answer('Po\u017eiadavka bola ozna\u010den\u00e1 ako zamietnut\u00e1. Product Truth sa nezmenil.')
        return
    if result == REVIEW_RESULT_ALREADY_PROCESSED:
        await message.answer('Po\u017eiadavka u\u017e bola spracovan\u00e1.')
        return
    if result == REVIEW_RESULT_NOT_FOUND:
        await message.answer('Po\u017eiadavku som nena\u0161iel.')
        return

    await message.answer('Po\u017eiadavku sa nepodarilo spracova\u0165.')


async def _start_customization_request_reply(message: Message, config: Config, state: FSMContext) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    request_id_or_prefix = _parse_text_arg(message.text or '')
    if request_id_or_prefix is None:
        await message.answer('Použitie: /customization_request_reply <request_id>')
        return

    service = CustomizationRequestService(config.db_path)
    lookup_result, request = _lookup_customization_request_for_admin(
        service=service,
        request_id_or_prefix=request_id_or_prefix,
    )
    if lookup_result != 'found' or request is None:
        await _answer_customization_request_lookup_failure(message, lookup_result)
        return

    admin_telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    if admin_telegram_id is None:
        await message.answer('Nepodarilo sa identifikovať správcu. Odpoveď nebola odoslaná.')
        return

    draft = {
        'response_id': f'crr_{uuid4().hex}',
        'request_id': request.request_id,
        'target_telegram_id': request.telegram_id,
        'target_workspace_id': request.workspace_id,
        'admin_telegram_id': int(admin_telegram_id),
        'response_kind': RESPONSE_KIND_ANSWER,
        'response_text': None,
        'request_status_at_draft': request.status,
        'request_title_preview': _safe_display_text(request.normalized_title, max_length=120),
        'created_at': _utc_timestamp(),
    }
    await state.update_data(**{_CUSTOMIZATION_RESPONSE_DRAFT_KEY: draft})
    await state.set_state(CustomizationRequestAdminResponseStates.waiting_response_text)
    await message.answer(
        'Napíšte odpoveď pre používateľa. Nepíšte interné poznámky, tajné údaje ani sľuby implementácie.'
    )


async def _send_customization_request_response(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    draft: dict,
    bot: Bot | None,
) -> None:
    service = CustomizationRequestService(config.db_path)
    request_id = str(draft.get('request_id') or '').strip()
    response_id = str(draft.get('response_id') or '').strip()
    response_text = str(draft.get('response_text') or '').strip()
    response_kind = str(draft.get('response_kind') or RESPONSE_KIND_ANSWER)
    admin_telegram_id = _draft_int(draft.get('admin_telegram_id'))
    if not request_id or not response_id or not response_text or admin_telegram_id is None:
        await state.clear()
        await message.answer('Návrh odpovede už nie je platný. Odpoveď nebola odoslaná.')
        return

    result, record = service.persist_customization_request_response_attempt(
        request_id=request_id,
        admin_telegram_id=admin_telegram_id,
        response_id=response_id,
        response_text=response_text,
        response_kind=response_kind,
    )
    if result == RESPONSE_RESULT_ALREADY_SENT:
        await state.clear()
        await message.answer(_CUSTOMIZATION_RESPONSE_ALREADY_SENT_MESSAGE)
        return
    if result == RESPONSE_RESULT_ALREADY_IN_PROGRESS:
        await state.clear()
        await message.answer(_CUSTOMIZATION_RESPONSE_IN_PROGRESS_MESSAGE)
        return
    if result == RESPONSE_RESULT_ALREADY_FAILED:
        await state.clear()
        await message.answer(_CUSTOMIZATION_RESPONSE_ALREADY_FAILED_MESSAGE)
        return
    if result == RESPONSE_RESULT_NOT_FOUND or record is None:
        await state.clear()
        await message.answer('Požiadavku som nenašiel. Odpoveď nebola odoslaná.')
        return
    if result != RESPONSE_RESULT_CLAIMED_FOR_SEND:
        await state.clear()
        await message.answer('Odpoveď sa nepodarilo pripraviť na odoslanie.')
        return

    target_telegram_id = record.telegram_id
    delivery_bot = bot or getattr(message, 'bot', None)
    user_text = _format_customization_response_for_user(record.admin_response_text or response_text)
    if delivery_bot is None or not hasattr(delivery_bot, 'send_message'):
        service.mark_response_delivery_failed(
            request_id=request_id,
            response_id=response_id,
            failed_reason='missing_bot',
        )
        await state.clear()
        await message.answer(_CUSTOMIZATION_RESPONSE_FAILED_MESSAGE)
        return

    try:
        await delivery_bot.send_message(target_telegram_id, user_text)
    except Exception:
        logger.exception('customization_request_response_delivery_failed request_id=%s', _short_request_id(request_id))
        service.mark_response_delivery_failed(
            request_id=request_id,
            response_id=response_id,
            failed_reason='telegram_send_failed',
        )
        await state.clear()
        await message.answer(_CUSTOMIZATION_RESPONSE_FAILED_MESSAGE)
        return

    try:
        mark_result, _ = service.mark_response_delivery_succeeded(request_id=request_id, response_id=response_id)
    except Exception:
        logger.exception('customization_request_response_success_status_update_failed request_id=%s', _short_request_id(request_id))
        await state.clear()
        await message.answer(_CUSTOMIZATION_RESPONSE_STATUS_UPDATE_FAILED_MESSAGE)
        return
    if mark_result not in {RESPONSE_RESULT_PREPARED, RESPONSE_RESULT_ALREADY_SENT}:
        logger.error(
            'customization_request_response_success_status_unexpected request_id=%s result=%s',
            _short_request_id(request_id),
            mark_result,
        )
        await state.clear()
        await message.answer(_CUSTOMIZATION_RESPONSE_STATUS_UPDATE_FAILED_MESSAGE)
        return
    await state.clear()
    await message.answer(_CUSTOMIZATION_RESPONSE_SENT_MESSAGE)


@router.message(Command('approve'))
async def cmd_approve(message: Message, config: Config, bot: Bot | None = None) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať administrátora.')
        return

    command_parts = (message.text or '').strip().split()
    telegram_id = (
        message.from_user.id
        if len(command_parts) == 1
        else _parse_telegram_id_arg(message.text or '')
    )
    if telegram_id is None:
        await message.answer('Pouzitie: /approve <telegram_id>')
        return

    access_service = AccessControlService(config.db_path)
    try:
        approval = access_service.approve_user(
            telegram_id=telegram_id,
            approved_by=message.from_user.id,
        )
    except AccessApprovalWorkspaceConflict as exc:
        logger.warning(
            'access_user_approval_workspace_conflict telegram_id=%s reason=%s',
            _mask_telegram_id(telegram_id),
            str(exc),
        )
        await message.answer(
            'Schválenie sa nevykonalo: existujúce vlastníctvo business workspace '
            'nie je jednoznačné. Žiadne údaje neboli zmenené.'
        )
        return
    logger.info(
        'access_user_approved telegram_id=%s approved_by=%s '
        'workspace_membership_reactivated=%s active_selection_restored=%s',
        _mask_telegram_id(telegram_id),
        _mask_telegram_id(message.from_user.id),
        approval.reactivated_workspace_membership,
        approval.restored_active_selection,
    )

    notification_bot = bot or getattr(message, 'bot', None)
    notification_sent = await _notify_approved_user(bot=notification_bot, telegram_id=telegram_id)
    if notification_sent:
        await message.answer(f'Pouzivatel {telegram_id} bol schvaleny. Pouzivatel dostal instrukcie pre /start.')
        return

    await message.answer(
        f'Pouzivatel {telegram_id} bol schvaleny, ale notifikaciu sa nepodarilo odoslat. '
        'Poslite mu prosim instrukciu: /start.'
    )


@router.message(Command('reject'))
async def cmd_reject(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    telegram_id = _parse_telegram_id_arg(message.text or '')
    if telegram_id is None:
        await message.answer('Pouzitie: /reject <telegram_id>')
        return

    AccessControlService(config.db_path).reject_user(
        telegram_id=telegram_id,
        decided_by=message.from_user.id,
    )
    await message.answer(f'Ziadost pouzivatela {telegram_id} bola zamietnuta.')


@router.message(Command('block'))
async def cmd_block(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    telegram_id = _parse_telegram_id_arg(message.text or '')
    if telegram_id is None:
        await message.answer('Pouzitie: /block <telegram_id>')
        return

    AccessControlService(config.db_path).block_user(
        telegram_id=telegram_id,
        decided_by=message.from_user.id,
    )
    await message.answer(f'Pouzivatel {telegram_id} bol zablokovany.')


@router.message(Command('users'))
async def cmd_users(message: Message, config: Config) -> None:
    await _send_users(message, config)


@router.message(
    StateFilter(None),
    lambda message: _normalize_alias(message.text or '') in _USERS_ALIASES,
)
async def users_alias(message: Message, config: Config) -> None:
    await _send_users(message, config)


async def _send_users(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    users = AccessControlService(config.db_path).list_authorized_users()
    if not users:
        await message.answer('Nie su ziadni autorizovani pouzivatelia v databaze.')
        return

    lines = ['Autorizovani pouzivatelia:']
    for user in users:
        lines.append(f'- telegram_id={user.telegram_id}, role={user.role}, status={user.status}')
    await message.answer('\n'.join(lines))


def _is_admin_message(message: Message, config: Config) -> bool:
    telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    return is_admin_telegram_user(config, telegram_id)


def _parse_telegram_id_arg(text: str) -> int | None:
    value = _parse_text_arg(text)
    if value is None:
        return None
    try:
        telegram_id = int(value)
    except ValueError:
        return None
    return telegram_id if telegram_id > 0 else None


def _parse_text_arg(text: str) -> str | None:
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None
    value = parts[1].strip()
    return value or None


def _lookup_customization_request_for_admin(
    *,
    service: CustomizationRequestService,
    request_id_or_prefix: str,
) -> tuple[str, CustomizationRequestRecord | None]:
    request = service.get_customization_request_by_id_for_admin(request_id=request_id_or_prefix)
    if request is not None:
        return 'found', request

    if len(request_id_or_prefix) < _CUSTOMIZATION_REQUEST_DETAIL_PREFIX_MIN_LENGTH:
        return 'too_short', None

    matches = service.find_customization_requests_by_id_prefix_for_admin(
        request_id_prefix=request_id_or_prefix,
        limit=2,
    )
    if not matches:
        return 'not_found', None
    if len(matches) > 1:
        return 'ambiguous', None
    return 'found', matches[0]


async def _answer_customization_request_lookup_failure(message: Message, lookup_result: str) -> None:
    if lookup_result == 'too_short':
        await message.answer(
            'Po\u017eiadavku som nena\u0161iel. Zadajte cel\u00fd request_id alebo aspo\u0148 '
            f'{_CUSTOMIZATION_REQUEST_DETAIL_PREFIX_MIN_LENGTH} znakov za\u010diatku ID.'
        )
        return
    if lookup_result == 'ambiguous':
        await message.answer('Na\u0161iel som viac po\u017eiadaviek s t\u00fdmto za\u010diatkom ID. Pou\u017eite dlh\u0161\u00ed request_id.')
        return
    await message.answer('Po\u017eiadavku som nena\u0161iel.')


def _review_command_name(decision: str) -> str:
    if decision == STATUS_REVIEWED_ACCEPTED:
        return 'customization_request_accept'
    return 'customization_request_reject'


def _normalize_alias(value: str) -> str:
    text = value.strip().lower().replace('_', ' ')
    normalized = unicodedata.normalize('NFKD', text)
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_diacritics).strip()


def _format_access_request_line(
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    status: str,
) -> str:
    username_value = username or '-'
    full_name = ' '.join(part for part in [first_name, last_name] if part).strip() or '-'
    return f'- telegram_id={telegram_id}, username={username_value}, meno={full_name}, status={status}'


def _format_customization_request_lines(request: CustomizationRequestRecord) -> list[str]:
    request_id = _short_request_id(request.request_id)
    created_at = _safe_display_text(request.created_at, max_length=32)
    workspace_id = _safe_display_text(request.workspace_id or '-', max_length=60)
    triage_class = _safe_display_text(request.source_triage_class, max_length=60)
    title = _safe_display_text(request.normalized_title, max_length=90)
    summary = _safe_display_text(request.normalized_summary, max_length=180)
    capability = _safe_display_text(request.source_capability_id or '-', max_length=80)
    status = _safe_display_text(request.status, max_length=40)
    return [
        '',
        f'- id={request_id}, created_at={created_at}',
        f'  telegram_id={request.telegram_id}, workspace_id={workspace_id}',
        f'  trieda={triage_class}, status={status}',
        f'  n\u00e1zov={title}',
        f'  zhrnutie={summary}',
        f'  capability_id={capability}',
    ]


def _format_customization_request_detail(request: CustomizationRequestRecord) -> str:
    response_delivery_state = _customization_response_delivery_state(request)
    lines = [
        'Detail po\u017eiadavky:',
        f'request_id={_safe_display_text(request.request_id, max_length=96)}',
        f'status={_safe_display_text(request.status, max_length=40)}',
        f'created_at={_safe_display_text(request.created_at, max_length=32)}',
        f'confirmed_at={_safe_display_text(request.confirmed_at or "-", max_length=32)}',
        f'telegram_id={request.telegram_id}',
        f'workspace_id={_safe_display_text(request.workspace_id or "-", max_length=80)}',
        f'source_channel={_safe_display_text(request.source_channel, max_length=30)}',
        f'source_triage_class={_safe_display_text(request.source_triage_class, max_length=70)}',
        f'source_capability_id={_safe_display_text(request.source_capability_id or "-", max_length=80)}',
        f'source_topic_id={_safe_display_text(request.source_topic_id or "-", max_length=80)}',
        f'privacy_redaction_flags={_safe_display_text(request.privacy_redaction_flags or "-", max_length=160)}',
        f'n\u00e1zov={_safe_display_text(request.normalized_title, max_length=160)}',
        f'zhrnutie={_safe_display_text(request.normalized_summary, max_length=700)}',
    ]
    if request.redacted_original_text:
        lines.append(f'redacted_original_text={_safe_display_text(request.redacted_original_text, max_length=900)}')
    lines.extend(
        [
            '',
            'Doru\u010denie odpovede:',
            f'response_delivery_status={_safe_display_text(response_delivery_state, max_length=40)}',
            f'response_kind={_safe_display_text(request.response_kind or "-", max_length=40)}',
            f'response_sent_at={_safe_display_text(request.response_sent_at or "-", max_length=32)}',
            f'response_sent_by={_safe_display_text(request.response_sent_by or "-", max_length=32)}',
            f'response_attempts={request.response_attempts}',
            f'responded_to_request_status={_safe_display_text(request.responded_to_request_status or "-", max_length=40)}',
            f'response_updated_at={_safe_display_text(request.response_updated_at or "-", max_length=32)}',
            f'response_id={_short_request_id(request.response_id) if request.response_id else "-"}',
        ]
    )
    if request.response_failed_reason:
        lines.append(
            f'response_failed_reason={_safe_display_text(request.response_failed_reason, max_length=80)}'
        )
    if _is_customization_response_send_pending_stuck(request):
        lines.append('response_delivery_warning=send_pending je star\u00fd viac ako 15 min\u00fat; v\u00fdsledok doru\u010denia je nezn\u00e1my a treba manu\u00e1lnu kontrolu.')
    if request.admin_response_text:
        lines.append(
            'admin_response_text_preview='
            f'{_safe_display_text(request.admin_response_text, max_length=500)}'
        )

    text = '\n'.join(lines)
    if len(text) <= _CUSTOMIZATION_REQUEST_DETAIL_MAX_MESSAGE_LENGTH:
        return text
    return text[: _CUSTOMIZATION_REQUEST_DETAIL_MAX_MESSAGE_LENGTH - 1].rstrip() + '\u2026'


def _format_customization_response_preview(draft: dict) -> str:
    request_id = _safe_display_text(draft.get('request_id'), max_length=96)
    target_telegram_id = _safe_display_text(draft.get('target_telegram_id'), max_length=32)
    response_text = _safe_display_text(draft.get('response_text'), max_length=1500)
    return (
        'Náhľad odpovede používateľovi\n\n'
        f'Požiadavka: {request_id}\n'
        f'Používateľ: {target_telegram_id}\n'
        'Typ odpovede: odpoveď\n\n'
        'Správa:\n'
        f'{response_text}\n\n'
        'Odoslať / Upraviť / Zrušiť'
    )


def _format_customization_response_for_user(response_text: str) -> str:
    return f'Odpoveď správcu k vašej požiadavke:\n\n{response_text}'


def _clean_response_text(value: str) -> str | None:
    text = redact_customization_request_text(value)
    if text is None:
        return None
    return text.strip() or None


def _customization_response_delivery_state(request: CustomizationRequestRecord) -> str:
    if not request.response_delivery_status and not request.response_id:
        return 'not_started'
    if request.response_delivery_status in {
        RESPONSE_DELIVERY_PENDING,
        RESPONSE_DELIVERY_SUCCEEDED,
        RESPONSE_DELIVERY_FAILED,
    }:
        return request.response_delivery_status
    return request.response_delivery_status or 'unknown'


def _is_customization_response_send_pending_stuck(request: CustomizationRequestRecord) -> bool:
    if request.response_delivery_status != RESPONSE_DELIVERY_PENDING:
        return False
    if request.response_attempts <= 0:
        return False
    if request.response_sent_at:
        return False
    updated_at = _parse_utc_timestamp(request.response_updated_at)
    if updated_at is None:
        return False
    age = datetime.now(UTC) - updated_at
    return age.total_seconds() >= _CUSTOMIZATION_RESPONSE_PENDING_STUCK_MINUTES * 60


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _draft_int(value: object | None) -> int | None:
    try:
        integer = int(value) if value is not None else 0
    except (TypeError, ValueError):
        return None
    return integer if integer > 0 else None


def _is_response_draft_owner(message: Message, draft: dict) -> bool:
    current_admin_id = getattr(getattr(message, 'from_user', None), 'id', None)
    draft_admin_id = _draft_int(draft.get('admin_telegram_id'))
    return current_admin_id is not None and draft_admin_id == int(current_admin_id)


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _short_request_id(request_id: str) -> str:
    clean_id = _safe_display_text(request_id, max_length=64)
    if len(clean_id) <= 14:
        return clean_id
    return f'{clean_id[:10]}\u2026{clean_id[-4:]}'


def _safe_display_text(value: object | None, *, max_length: int) -> str:
    redacted = redact_customization_request_text(str(value or '')) or '-'
    compacted = re.sub(r'\s+', ' ', redacted).strip() or '-'
    if len(compacted) <= max_length:
        return compacted
    return compacted[: max_length - 1].rstrip() + '\u2026'


async def _notify_approved_user(*, bot: Bot | None, telegram_id: int) -> bool:
    if bot is None or not hasattr(bot, 'send_message'):
        logger.warning('access_approval_notification_skipped telegram_id=%s reason=no_bot', _mask_telegram_id(telegram_id))
        return False
    try:
        await bot.send_message(telegram_id, APPROVED_ACCESS_NEXT_STEP_MESSAGE)
    except Exception:
        logger.exception('access_approval_notification_failed telegram_id=%s', _mask_telegram_id(telegram_id))
        return False
    logger.info('access_approval_notification_sent telegram_id=%s', _mask_telegram_id(telegram_id))
    return True


def _mask_telegram_id(telegram_id: int | None) -> str:
    if telegram_id is None:
        return '-'
    value = str(telegram_id)
    if len(value) <= 4:
        return '***'
    return f'{value[:2]}***{value[-2:]}'
