from __future__ import annotations

from datetime import datetime, timezone
import logging
import re

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import Config
from bot.services.decision_resolver import resolve_yes_no
from bot.services.contact_registry_monitor import (
    CALLBACK_PREFIX,
    ContactRegistryMonitorService,
    DECISION_NO,
    DECISION_YES,
)


router = Router()
logger = logging.getLogger(__name__)
_CALLBACK_RE = re.compile(
    rf'^{CALLBACK_PREFIX}:(?P<decision>{DECISION_YES}|{DECISION_NO}):'
    r'(?P<proposal>[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-'
    r'[89ab][0-9a-f]{3}-[0-9a-f]{12})$'
)
_STALE = 'Tento návrh už nie je dostupný alebo nemáte oprávnenie.'


@router.callback_query(F.data.startswith(f'{CALLBACK_PREFIX}:'))
async def contact_registry_monitor_callback(
    callback: CallbackQuery, config: Config
) -> None:
    match = _CALLBACK_RE.fullmatch(callback.data or '')
    actor_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if match is None or actor_id is None:
        await callback.answer(_STALE, show_alert=True)
        return
    decision = await resolve_yes_no(
        context_name='contact_registry_monitor_proposal',
        user_input_text=match.group('decision'),
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision not in {DECISION_YES, DECISION_NO}:
        await callback.answer(_STALE, show_alert=True)
        return
    resolution = ContactRegistryMonitorService(config.db_path, config).resolve(
        proposal_id=match.group('proposal'),
        actor_telegram_id=int(actor_id),
        decision=decision,
        now=datetime.now(timezone.utc),
    )
    logger.info(
        'Contact registry proposal resolved proposal_id=%s actor_id=%s '
        'status=%s reason=%s affected_contacts=%s',
        match.group('proposal'),
        actor_id,
        resolution.status,
        resolution.reason,
        resolution.affected_contacts,
    )
    if resolution.status == 'applied':
        await _clear_keyboard(callback, proposal_id=match.group('proposal'))
        if resolution.affected_contacts > 1:
            applied_text = (
                f'Aktualizované kontakty: {resolution.affected_contacts} pre firmu '
                f'„{resolution.contact_name}“. Už vystavené faktúry a PDF zostali '
                'bez zmeny.'
            )
        else:
            applied_text = (
                f'Kontakt „{resolution.contact_name}“ bol aktualizovaný. '
                'Už vystavené faktúry a PDF zostali bez zmeny.'
            )
        await _answer_message(
            callback,
            applied_text,
        )
        await callback.answer()
        return
    if resolution.status == 'dismissed':
        await _clear_keyboard(callback, proposal_id=match.group('proposal'))
        if resolution.affected_contacts > 1:
            dismissed_text = (
                f'Kontakty zostali bez zmeny ({resolution.affected_contacts} profilov).'
            )
        else:
            dismissed_text = 'Kontakt zostal bez zmeny.'
        await _answer_message(callback, dismissed_text)
        await callback.answer()
        return
    if resolution.status in {'stale', 'expired', 'conflict'}:
        await _clear_keyboard(callback, proposal_id=match.group('proposal'))
        if resolution.status == 'expired':
            text = 'Platnosť tejto kontroly už vypršala. Kontakt nebol zmenený.'
        elif resolution.status == 'conflict':
            text = (
                'Aktualizáciu nemožno bezpečne použiť, pretože názov alebo IČO '
                'koliduje s iným kontaktom. Nič som nezmenil.'
            )
        else:
            text = (
                'Kontakt alebo tento návrh sa medzičasom zmenil. Nič som nezmenil; '
                'ďalšia kontrola vytvorí nový návrh, ak bude stále potrebný.'
            )
        await _answer_message(callback, text)
        await callback.answer()
        return
    await callback.answer(_STALE, show_alert=True)


async def _clear_keyboard(callback: CallbackQuery, *, proposal_id: str) -> None:
    if callback.message is None or not hasattr(callback.message, 'edit_reply_markup'):
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.warning(
            'Contact registry proposal keyboard cleanup failed proposal_id=%s',
            proposal_id,
            exc_info=True,
        )


async def _answer_message(callback: CallbackQuery, text: str) -> None:
    if callback.message is not None and hasattr(callback.message, 'answer'):
        await callback.message.answer(text)
