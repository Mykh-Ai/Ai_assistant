from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.config import Config
from bot.services.contextual_info_help_recovery import (
    GENUINELY_UNCLEAR_MESSAGE,
    action_label,
    action_metadata,
    contextual_recovery_store,
    default_recovery_action_ids,
    default_recovery_capability_ids,
    resolve_contextual_recovery,
)
from bot.services.conversation_context import (
    conversation_context_service,
    current_active_conversation_turn,
    remember_callback_label,
)
from bot.services.product_truth import get_capability
from bot.services.workspace_context import WorkspaceContextService


router = Router(name='info_help_recovery')
logger = logging.getLogger(__name__)


@router.callback_query(F.data == 'navigation:show_main_menu')
async def show_main_menu_navigation(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    message = callback.message
    actor = callback.from_user
    if message is None or actor is None or getattr(message, 'chat', None) is None:
        await callback.answer('Táto voľba už nie je dostupná.', show_alert=True)
        return
    if await state.get_state() is None:
        await callback.answer('Rozpracovaná akcia už nie je aktívna.', show_alert=True)
        return
    try:
        await callback.answer()
        await message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception('Failed to remove owned active-FSM navigation keyboard')
    remember_callback_label(
        user_id=int(actor.id), chat_id=int(message.chat.id), label='Hlavné menu'
    )
    from bot.services.active_fsm_guard import clear_current_state_safely
    from bot.handlers.start import cmd_menu

    await clear_current_state_safely(state=state, config=config)
    await cmd_menu(message=message, config=config, state=state)


@router.callback_query(F.data.startswith('infohelp:'))
async def contextual_recovery_selection(
    callback: CallbackQuery,
    state: FSMContext,
    config: Config,
) -> None:
    message = callback.message
    actor = callback.from_user
    parsed = _parse_infohelp_callback(callback.data)
    if message is None or actor is None or getattr(message, 'chat', None) is None or parsed is None:
        await callback.answer('Neplatná voľba.', show_alert=True)
        return
    token, index = parsed
    workspace_id = _workspace_id(config, int(actor.id))
    status, action_id = contextual_recovery_store.consume_with_status(
        token,
        user_id=int(actor.id),
        chat_id=int(message.chat.id),
        workspace_id=workspace_id,
        index=index,
    )
    if status != 'consumed' or action_id is None:
        callback_errors = {
            'expired': 'Táto voľba vypršala.',
            'duplicate': 'Táto voľba už bola použitá.',
            'forbidden': 'Táto voľba patrí inému používateľovi alebo profilu.',
            'invalid_index': 'Neplatná možnosť.',
            'missing': 'Táto voľba už neexistuje.',
        }
        await callback.answer(callback_errors.get(status, 'Neplatná voľba.'), show_alert=True)
        return
    metadata = action_metadata(action_id)
    if metadata is None:
        await callback.answer('Táto voľba už nie je podporovaná.', show_alert=True)
        return
    truth = get_capability(str(metadata['capability_id']))
    if truth.product_status.value in {'planned', 'unsupported', 'unknown'}:
        from bot.services.info_help import build_product_truth_guidance_for_capability

        try:
            await callback.answer()
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.exception('Failed to remove owned unsupported-recovery keyboard')
        await message.answer(build_product_truth_guidance_for_capability(
            str(metadata['capability_id'])
        ))
        return
    try:
        await callback.answer()
        await message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception('Failed to remove owned contextual-recovery keyboard')
    remember_callback_label(
        user_id=int(actor.id), chat_id=int(message.chat.id), label=action_label(action_id)
    )
    await dispatch_recovery_action(
        action_id=action_id, message=message, state=state, config=config
    )


@router.message(lambda message: bool((message.text or '').strip().startswith('/')))
async def unknown_command_recovery(
    message: Message,
    state: FSMContext,
    config: Config,
) -> None:
    await handle_idle_contextual_recovery(
        message=message,
        state=state,
        config=config,
        text=(message.text or '').strip(),
        input_channel='command',
    )


async def handle_idle_contextual_recovery(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    text: str,
    input_channel: str,
) -> None:
    await state.clear()
    actor = getattr(message, 'from_user', None)
    chat = getattr(message, 'chat', None)
    from bot.services.customization_requests import REQUEST_STARTING_TRIAGE_CLASSES
    from bot.services.info_help import (
        TRIAGE_KNOWN_PRODUCT_CAPABILITY,
        TRIAGE_OUT_OF_DOMAIN,
        TRIAGE_SMALLTALK,
        TRIAGE_SPAM_OR_ABUSE,
        classify_info_help_triage,
        render_info_help_triage_result,
    )

    deterministic_triage = classify_info_help_triage(user_input_text=text)
    if deterministic_triage.triage_class in REQUEST_STARTING_TRIAGE_CLASSES:
        from bot.handlers.invoice import _start_customization_request_preview
        if actor is None:
            await message.answer('Nepodarilo sa identifikovať používateľa. Požiadavku som neuložil.')
            return

        await _start_customization_request_preview(
            message=message,
            state=state,
            requester_telegram_id=int(actor.id),
            user_input_text=text,
            source_channel=input_channel,
            triage_class=deterministic_triage.triage_class,
            capability_id=deterministic_triage.capability_id,
            topic_id=deterministic_triage.topic_id,
            confidence=deterministic_triage.confidence,
            business_need=deterministic_triage.business_need,
            detected_domain=deterministic_triage.detected_domain,
            expected_outcome=deterministic_triage.expected_outcome,
            clarification_questions=deterministic_triage.clarification_questions,
            proposed_title=deterministic_triage.proposed_title,
            proposed_description=deterministic_triage.proposed_description,
            risk_level=deterministic_triage.risk_level,
        )
        return
    if deterministic_triage.triage_class in {
        TRIAGE_KNOWN_PRODUCT_CAPABILITY,
        TRIAGE_OUT_OF_DOMAIN,
        TRIAGE_SMALLTALK,
        TRIAGE_SPAM_OR_ABUSE,
    }:
        deterministic_guidance = render_info_help_triage_result(deterministic_triage)
        if deterministic_guidance:
            await message.answer(deterministic_guidance)
            return
    active_turn = current_active_conversation_turn()
    if actor is None:
        await message.answer(GENUINELY_UNCLEAR_MESSAGE)
        return
    chat_id = int(chat.id) if chat is not None else (
        active_turn.chat_id if active_turn is not None else int(actor.id)
    )
    workspace_id = (
        active_turn.workspace_id if active_turn is not None
        else _workspace_id(config, int(actor.id))
    )
    recent_turns = [
        turn.to_prompt_dict()
        for turn in conversation_context_service.recent_turns(
            int(actor.id), chat_id, workspace_id
        )
    ]
    result = await resolve_contextual_recovery(
        user_input=text,
        input_channel=input_channel,
        recent_turns=recent_turns,
        active_state_descriptor=None,
        action_ids=default_recovery_action_ids(),
        capability_ids=default_recovery_capability_ids(),
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    candidates = (
        (result.action_id,) if result.outcome == 'resolved_action' and result.action_id
        else result.candidate_action_ids if result.outcome == 'clarify_candidates'
        else ()
    )
    if candidates:
        token = contextual_recovery_store.create(
            user_id=int(actor.id),
            chat_id=chat_id,
            workspace_id=workspace_id,
            candidate_action_ids=candidates,
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=action_label(action_id),
                callback_data=f'infohelp:{token}:{index}',
            )]
            for index, action_id in enumerate(candidates)
        ])
        await message.answer('Mali ste na mysli niektorú z týchto možností?', reply_markup=keyboard)
        return
    if result.outcome == 'unsupported_capability' and result.capability_id:
        from bot.services.info_help import build_product_truth_guidance_for_capability

        await message.answer(build_product_truth_guidance_for_capability(result.capability_id))
        return
    if result.outcome == 'new_business_feature_request':
        from bot.handlers.invoice import _start_customization_request_preview
        from bot.services.info_help import TRIAGE_NEW_BUSINESS_FEATURE_REQUEST

        await _start_customization_request_preview(
            message=message,
            state=state,
            requester_telegram_id=int(actor.id),
            user_input_text=text,
            source_channel=input_channel,
            triage_class=TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
            capability_id=result.capability_id or 'unknown',
            topic_id='customization_request',
            confidence=result.confidence,
            business_need=text,
            detected_domain=result.object_domain,
            expected_outcome=text,
            clarification_questions=(),
            proposed_title='Požiadavka na nový business workflow',
            proposed_description=text,
            risk_level='medium',
        )
        return
    await message.answer(GENUINELY_UNCLEAR_MESSAGE)


async def dispatch_recovery_action(
    *, action_id: str, message: Message, state: FSMContext, config: Config
) -> None:
    if action_id == 'start':
        from bot.handlers.start import cmd_start
        await cmd_start(message=message, config=config, state=state)
    elif action_id == 'create_invoice':
        from bot.handlers.invoice import cmd_invoice
        await cmd_invoice(message=message, state=state)
    elif action_id == 'show_supplier_profile':
        from bot.handlers.onboarding import cmd_moj_profil
        await cmd_moj_profil(message=message, state=state, config=config)
    elif action_id == 'edit_supplier':
        from bot.handlers.onboarding import cmd_upravit_profil
        await cmd_upravit_profil(message=message, state=state, config=config)
    elif action_id == 'add_contact':
        from bot.handlers.contacts import start_add_contact_intake
        await start_add_contact_intake(message=message, state=state, config=config)
    elif action_id == 'add_service_alias':
        from bot.handlers.supplier import start_add_service_alias_intake
        await start_add_service_alias_intake(message=message, state=state, config=config)
    elif action_id == 'show_recent_accounting_documents':
        from bot.handlers.accounting_documents import cmd_blocky
        await cmd_blocky(message=message, config=config, state=state)
    elif action_id == 'add_receipt':
        from bot.handlers.accounting_document_intake import cmd_accounting_document_intake
        await cmd_accounting_document_intake(message=message, state=state)
    elif action_id == 'delete_user_database':
        from bot.handlers.delete_user_database import start_delete_user_database_flow
        await start_delete_user_database_flow(message=message, state=state, config=config)
    elif action_id == 'open_work_day':
        from bot.handlers.work_time import start_open_work_day
        await start_open_work_day(message=message, state=state, config=config)
    elif action_id == 'close_work_day':
        from bot.handlers.work_time import start_close_work_day
        await start_close_work_day(message=message, state=state, config=config, text='')
    elif action_id == 'add_work_time_entry':
        from bot.handlers.work_time import start_add_work_time_entry
        await start_add_work_time_entry(message=message, state=state, config=config, text='')
    elif action_id == 'generate_work_time_report':
        from bot.handlers.work_time import start_generate_work_time_report
        await start_generate_work_time_report(
            message=message, state=state, config=config, text='', source_channel='callback'
        )
    elif action_id == 'delete_work_time_month':
        from bot.handlers.work_time import start_delete_work_time_month
        await start_delete_work_time_month(message=message, state=state, config=config, text='')
    elif action_id == 'update_work_time_lunch_break':
        from bot.handlers.work_time import start_update_work_time_lunch_break
        await start_update_work_time_lunch_break(
            message=message, state=state, config=config, text=''
        )
    elif action_id == 'switch_business_profile':
        from bot.handlers.business_profiles import start_switch_business_profile
        await start_switch_business_profile(
            message=message, state=state, config=config, profile_ref=None)
    elif action_id in {
        'show_existing_invoice', 'edit_existing_invoice',
        'delete_existing_invoice', 'mark_existing_invoice_paid',
        'invoice_analytics', 'accounting_document_analytics',
    }:
        from bot.handlers.invoice import process_invoice_text
        await process_invoice_text(
            message=message, state=state, config=config,
            invoice_text=action_label(action_id), input_channel='callback',
        )
    else:
        await message.answer(GENUINELY_UNCLEAR_MESSAGE)


def _parse_infohelp_callback(data: str | None) -> tuple[str, int] | None:
    parts = str(data or '').split(':')
    if len(parts) != 3 or parts[0] != 'infohelp' or not parts[1]:
        return None
    try:
        index = int(parts[2])
    except ValueError:
        return None
    return parts[1], index


def _workspace_id(config: Config, user_id: int) -> str | None:
    if not config.db_path.exists():
        return None
    try:
        return WorkspaceContextService(config.db_path).resolve_for_user_readonly(user_id).workspace_id
    except Exception:
        return None
