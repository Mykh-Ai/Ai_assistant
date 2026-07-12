from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.config import Config
from bot.handlers.onboarding import start_additional_supplier_profile_onboarding
from bot.services.decision_resolver import resolve_yes_no
from bot.services.semantic_action_resolver import resolve_semantic_action
from bot.services.workspace_context import (
    WorkspaceContext,
    WorkspaceContextError,
    WorkspaceContextService,
)


router = Router(name='business_profiles')

_ADD_PROFILE = 'Pridať firemný profil'
_CANCEL = 'Zrušiť'
_ACTIVE_PREFIX = 'Aktívny: '
_STATE_CANDIDATES_KEY = 'business_profile_candidates'
_STATE_PENDING_WORKSPACE_KEY = 'business_profile_pending_workspace_id'


class BusinessProfileStates(StatesGroup):
    waiting_selection = State()
    waiting_switch_confirm = State()


def _keyboard(contexts: list[WorkspaceContext], active_workspace_id: str | None) -> ReplyKeyboardMarkup:
    rows = []
    for context in contexts:
        label = context.workspace_display_name
        if context.workspace_id == active_workspace_id:
            label = f'{_ACTIVE_PREFIX}{label}'
        rows.append([KeyboardButton(text=label)])
    if any(context.membership_role == 'owner' for context in contexts):
        rows.append([KeyboardButton(text=_ADD_PROFILE)])
    rows.append([KeyboardButton(text=_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


def _remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove(remove_keyboard=True)


def _candidate_payload(contexts: list[WorkspaceContext]) -> list[dict[str, str]]:
    return [
        {
            'workspace_id': context.workspace_id,
            'label': context.workspace_display_name,
        }
        for context in contexts
    ]


def _match_context(contexts: list[WorkspaceContext], value: str) -> WorkspaceContext | None:
    normalized = value.strip().casefold()
    if normalized.startswith(_ACTIVE_PREFIX.casefold()):
        normalized = normalized[len(_ACTIVE_PREFIX):].strip()
    matches = [
        context
        for context in contexts
        if context.workspace_display_name.strip().casefold() == normalized
        or context.workspace_id.casefold() == normalized
    ]
    return matches[0] if len(matches) == 1 else None


async def _resolve_context_from_request(
    *,
    contexts: list[WorkspaceContext],
    user_text: str,
    config: Config,
) -> WorkspaceContext | None:
    exact = _match_context(contexts, user_text)
    if exact is not None:
        return exact
    normalized = user_text.strip().casefold()
    contained = [
        context
        for context in contexts
        if context.workspace_display_name.strip().casefold() in normalized
    ]
    if len(contained) == 1:
        return contained[0]
    allowed = [context.workspace_id for context in contexts]
    if not allowed:
        return None
    resolved = await resolve_semantic_action(
        context_name='business_profile_ref',
        allowed_actions=[*allowed, 'unknown'],
        user_input_text=user_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        action_hints={
            context.workspace_id: {
                'meaning': f'business profile named {context.workspace_display_name}',
            }
            for context in contexts
        },
    )
    return next(
        (context for context in contexts if context.workspace_id == resolved),
        None,
    )

async def _accessible_contexts(message: Message, config: Config) -> list[WorkspaceContext] | None:
    telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return None
    try:
        return WorkspaceContextService(config.db_path).list_accessible_workspaces(telegram_id)
    except WorkspaceContextError:
        await message.answer('Business profily nie sú dostupné pre tento účet.')
        return None


async def _show_selector(message: Message, state: FSMContext, config: Config) -> None:
    contexts = await _accessible_contexts(message, config)
    if contexts is None:
        return
    if not contexts:
        await message.answer('Nemáte vytvorený business profil. Použite /moj_profil.')
        return
    telegram_id = message.from_user.id
    try:
        active_workspace_id = WorkspaceContextService(config.db_path).resolve_for_user(telegram_id).workspace_id
    except WorkspaceContextError:
        active_workspace_id = None
    await state.update_data(**{_STATE_CANDIDATES_KEY: _candidate_payload(contexts)})
    await state.set_state(BusinessProfileStates.waiting_selection)
    lines = ['Firemné profily:']
    for context in contexts:
        marker = ' (aktívny)' if context.workspace_id == active_workspace_id else ''
        lines.append(f'- {context.workspace_display_name}{marker}')
    await message.answer(
        '\n'.join(lines),
        reply_markup=_keyboard(contexts, active_workspace_id),
    )


async def _switch_blocked_by_active_flow(message: Message, state: FSMContext) -> bool:
    current_state = await state.get_state()
    allowed_states = {
        None,
        BusinessProfileStates.waiting_selection.state,
        BusinessProfileStates.waiting_switch_confirm.state,
    }
    if current_state in allowed_states:
        return False
    await message.answer(
        'Aktívny proces patrí aktuálnemu business profilu. '
        'Najprv ho dokončite alebo zrušte; profil sa nezmenil.'
    )
    return True


@router.message(Command('profily'))
async def cmd_business_profiles(message: Message, state: FSMContext, config: Config) -> None:
    if await _switch_blocked_by_active_flow(message, state):
        return
    await _show_selector(message, state, config)


async def start_switch_business_profile(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    profile_ref: str | None = None,
    source_channel: str = 'text',
) -> None:
    if await _switch_blocked_by_active_flow(message, state):
        return
    contexts = await _accessible_contexts(message, config)
    if contexts is None:
        return
    target = (
        await _resolve_context_from_request(
            contexts=contexts,
            user_text=profile_ref,
            config=config,
        )
        if profile_ref
        else None
    )
    if target is None:
        await _show_selector(message, state, config)
        return
    if source_channel == 'voice':
        await state.update_data(**{_STATE_PENDING_WORKSPACE_KEY: target.workspace_id})
        await state.set_state(BusinessProfileStates.waiting_switch_confirm)
        await message.answer(
            f'Prepnúť aktívny firemný profil na {target.workspace_display_name}? '
            'Odpovedzte ano alebo nie.'
        )
        return
    await _activate(message=message, state=state, config=config, target=target)


async def _activate(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    target: WorkspaceContext,
) -> None:
    WorkspaceContextService(config.db_path).set_active_workspace(
        target.actor_telegram_id,
        target.workspace_id,
    )
    await state.clear()
    await message.answer(
        f'Aktívny firemný profil bol zmenený na {target.workspace_display_name}.',
        reply_markup=_remove_keyboard(),
    )


@router.message(BusinessProfileStates.waiting_selection)
async def business_profile_selection(message: Message, state: FSMContext, config: Config) -> None:
    text = (message.text or '').strip()
    if text.casefold() == _CANCEL.casefold():
        await state.clear()
        await message.answer('Výber profilu bol zrušený.', reply_markup=_remove_keyboard())
        return
    if text.casefold() == _ADD_PROFILE.casefold():
        contexts = await _accessible_contexts(message, config)
        if contexts is None:
            return
        if not any(context.membership_role == 'owner' for context in contexts):
            await message.answer('Pridať profil môže iba vlastník workspace.')
            return
        await start_additional_supplier_profile_onboarding(message, state)
        return
    contexts = await _accessible_contexts(message, config)
    if contexts is None:
        return
    target = _match_context(contexts, text)
    if target is None:
        await message.answer('Vyberte presný profil zo zoznamu alebo zrušte výber.')
        return
    await _activate(message=message, state=state, config=config, target=target)


@router.message(BusinessProfileStates.waiting_switch_confirm)
async def business_profile_switch_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
    canonical_decision: str | None = None,
) -> None:
    decision = canonical_decision or await resolve_yes_no(
        context_name='business_profile_switch_confirm',
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer('Napíšte ano alebo nie.')
        return
    if decision == 'no':
        await state.clear()
        await message.answer('Aktívny profil sa nezmenil.', reply_markup=_remove_keyboard())
        return
    data = await state.get_data()
    workspace_id = str(data.get(_STATE_PENDING_WORKSPACE_KEY) or '').strip()
    contexts = await _accessible_contexts(message, config)
    if contexts is None:
        await state.clear()
        return
    target = next((item for item in contexts if item.workspace_id == workspace_id), None)
    if target is None:
        await state.clear()
        await message.answer('Vybraný business profil už nie je dostupný.', reply_markup=_remove_keyboard())
        return
    await _activate(message=message, state=state, config=config, target=target)