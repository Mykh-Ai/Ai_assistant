from __future__ import annotations

import logging
import re
import sqlite3
from enum import Enum
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, Update

from bot.config import Config
from bot.services.authorization import is_admin_telegram_user
from bot.services.runtime_issue import (
    RuntimeIssueCaptureInput,
    RuntimeIssueError,
    RuntimeIssueInvalidInput,
    RuntimeIssueService,
    RuntimeIssueUnsafeInput,
)
from bot.services.semantic_action_resolver import resolve_semantic_action
from bot.services.workspace_context import WorkspaceContextError, WorkspaceContextService


RUNTIME_ISSUE_ACTION = 'report_runtime_issue'
RUNTIME_ISSUE_USAGE = (
    'Opíšte problém v tej istej správe: /issue po stlačení tlačidla sa '
    'nezobrazilo potvrdenie.\nAktuálnu akciu bota som nezrušil.'
)
RUNTIME_ISSUE_INVALID = (
    'Problém sa nepodarilo bezpečne uložiť. Pošlite nový úplný opis bez '
    'hesiel, tokenov, súkromných kľúčov alebo výpisu prostredia. '
    'Aktuálna akcia bota zostala nezmenená.'
)
RUNTIME_ISSUE_FAILURE = (
    'Problém sa nepodarilo uložiť. Skúste to neskôr. '
    'Aktuálna akcia bota zostala nezmenená.'
)

RUNTIME_ISSUE_PREFIX_MARKERS = frozenset(
    {'проблема', 'помилка', 'баг', 'chyba', 'problem', 'bug', 'error'}
)
_RUNTIME_ISSUE_PREFIX_RE = re.compile(r'^\s*[\W_]*?([^\W\d_]+)(?!\w)(.*)$', re.UNICODE)

router = Router(name='runtime_issue')
logger = logging.getLogger(__name__)


class RuntimeIssueAdminCheck(str, Enum):
    ADMIN = 'admin'
    NOT_ADMIN = 'not_admin'
    FAILED = 'admin_check_failed'


def check_runtime_issue_admin(
    config: Config,
    actor_telegram_id: int | None,
) -> RuntimeIssueAdminCheck:
    """Keep a technical read failure distinct from a truthful non-admin result."""
    if actor_telegram_id is None:
        return RuntimeIssueAdminCheck.NOT_ADMIN
    try:
        if not config.db_path.is_file():
            return RuntimeIssueAdminCheck.FAILED
        if is_admin_telegram_user(config, actor_telegram_id):
            return RuntimeIssueAdminCheck.ADMIN
    except (OSError, sqlite3.Error):
        return RuntimeIssueAdminCheck.FAILED
    return RuntimeIssueAdminCheck.NOT_ADMIN


def is_runtime_issue_admin(config: Config, actor_telegram_id: int | None) -> bool:
    """Fail closed without creating a database during a read-only intent probe."""
    return (
        check_runtime_issue_admin(config, actor_telegram_id)
        == RuntimeIssueAdminCheck.ADMIN
    )


def extract_runtime_issue_command(text: str) -> str | None:
    stripped = text.strip()
    if not stripped.startswith('/'):
        return None
    token, separator, remainder = stripped.partition(' ')
    if token.split('@', 1)[0].casefold() != '/issue':
        return None
    return remainder.strip() if separator else ''


def extract_runtime_issue_prefix_description(text: str) -> str | None:
    """Return the description after an explicit first-token problem marker."""
    match = _RUNTIME_ISSUE_PREFIX_RE.match(text)
    if match is None:
        return None
    marker = match.group(1).casefold()
    if marker not in RUNTIME_ISSUE_PREFIX_MARKERS:
        return None
    return match.group(2).lstrip(' \t\r\n:;,.!?-–—').strip()


async def resolve_runtime_issue_intent(
    *,
    text: str,
    config: Config,
    current_state: str | None,
    input_channel: str,
) -> bool:
    decision = await resolve_semantic_action(
        context_name='runtime_issue_intent',
        allowed_actions=[RUNTIME_ISSUE_ACTION, 'unknown'],
        user_input_text=text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
        auxiliary_context={
            'current_state': current_state,
            'input_channel': input_channel,
            'administrator_authorized': True,
        },
        action_hints={
            RUNTIME_ISSUE_ACTION: {
                'meaning': (
                    'administrator explicitly asks to store one concrete observed '
                    'bot/runtime problem as an issue; Python stores only the report '
                    'and does not diagnose, repair, replay, or deploy anything'
                ),
                'positive_examples': [
                    'Po uložení bločku zostala stará klávesnica; ulož to ako problém.',
                    'Nahlás chybu: po potvrdení sa správa nezobrazila.',
                ],
                'not_this': [
                    'capability or usage question about reporting problems',
                    'feature or customization request',
                    'ordinary invoice, contact, supplier profile, receipt, accounting document, or work-time action',
                    'ordinary active-FSM answer',
                    'generic dissatisfaction or text merely containing bug, issue, error, or chyba',
                ],
            }
        },
    )
    return decision == RUNTIME_ISSUE_ACTION


async def handle_runtime_issue_capture(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    description: str,
    source_channel: str,
    telegram_update_id: int | None,
) -> bool:
    actor_telegram_id = _trusted_actor_id(message)
    admin_check = check_runtime_issue_admin(config, actor_telegram_id)
    if admin_check == RuntimeIssueAdminCheck.FAILED:
        await message.answer(RUNTIME_ISSUE_FAILURE)
        return True
    if admin_check != RuntimeIssueAdminCheck.ADMIN:
        return False

    telegram_message_id = _trusted_int(getattr(message, 'message_id', None))
    telegram_chat_id = _trusted_chat_id(message)
    if (
        actor_telegram_id is None
        or telegram_update_id is None
        or telegram_message_id is None
        or telegram_chat_id is None
    ):
        await message.answer(RUNTIME_ISSUE_FAILURE)
        return True

    try:
        current_state = await state.get_state()
        state_data = await state.get_data()
        workspace_id, workspace_resolution_reason = _resolve_workspace(
            config=config,
            actor_telegram_id=actor_telegram_id,
        )
        result = RuntimeIssueService(config.db_path).capture(
            RuntimeIssueCaptureInput(
                description=description,
                actor_telegram_id=actor_telegram_id,
                telegram_update_id=telegram_update_id,
                telegram_message_id=telegram_message_id,
                telegram_chat_id=telegram_chat_id,
                workspace_id=workspace_id,
                workspace_resolution_reason=workspace_resolution_reason,
                source_channel=source_channel,
                active_fsm_state=current_state,
                active_fsm_data=state_data,
                reported_build_sha=None,
                build_sha_status='unavailable',
            )
        )
    except (RuntimeIssueUnsafeInput, RuntimeIssueInvalidInput):
        await message.answer(RUNTIME_ISSUE_INVALID)
        return True
    except (RuntimeIssueError, RuntimeError, OSError, sqlite3.Error):
        logger.exception('Runtime issue intake failed')
        await message.answer(RUNTIME_ISSUE_FAILURE)
        return True

    if result.duplicate:
        response = (
            f'Problém už je uložený ako {result.record.issue_id}. '
            'Nevytvoril som druhý záznam. Aktuálna akcia bota zostala nezmenená.'
        )
    else:
        response = (
            f'Problém som uložil ako {result.record.issue_id}. '
            'Záznam nepotvrdzuje, že ide o chybu, ani nesľubuje opravu. '
            'Aktuálna akcia bota zostala nezmenená.'
        )
    await message.answer(response)
    return True


@router.message(Command('issue'))
async def cmd_runtime_issue(
    message: Message,
    state: FSMContext,
    config: Config,
    event_update: Update,
) -> None:
    actor_telegram_id = _trusted_actor_id(message)
    admin_check = check_runtime_issue_admin(config, actor_telegram_id)
    if admin_check == RuntimeIssueAdminCheck.FAILED:
        await message.answer(RUNTIME_ISSUE_FAILURE)
        return
    if admin_check != RuntimeIssueAdminCheck.ADMIN:
        return
    description = extract_runtime_issue_command(message.text or '')
    if not description:
        await message.answer(RUNTIME_ISSUE_USAGE)
        return
    await handle_runtime_issue_capture(
        message=message,
        state=state,
        config=config,
        description=description,
        source_channel='text',
        telegram_update_id=_trusted_int(getattr(event_update, 'update_id', None)),
    )


def _resolve_workspace(*, config: Config, actor_telegram_id: int) -> tuple[str | None, str]:
    try:
        context = WorkspaceContextService(config.db_path).resolve_for_user_readonly(
            actor_telegram_id
        )
    except WorkspaceContextError:
        return None, 'no_active_workspace'
    return context.workspace_id, 'active_workspace'


def _trusted_actor_id(message: Message) -> int | None:
    from_user = getattr(message, 'from_user', None)
    return _trusted_int(getattr(from_user, 'id', None))


def _trusted_chat_id(message: Message) -> int | None:
    chat = getattr(message, 'chat', None)
    return _trusted_int(getattr(chat, 'id', None))


def _trusted_int(value: Any) -> int | None:
    return value if isinstance(value, int) else None
