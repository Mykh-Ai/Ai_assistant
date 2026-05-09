from __future__ import annotations

import re
from typing import Any
import unicodedata

from bot.services.semantic_action_resolver import resolve_bounded_confirmation_reply


ApproveEditCancelDecision = str
YesNoDecision = str
AttachmentRouteChoiceDecision = str
AttachmentDocumentTypeChoiceDecision = str
GlobalCancelDecision = str

_UNKNOWN = 'unknown'
_APPROVE_EDIT_CANCEL_OUTPUTS = ['schvalit', 'upravit', 'zrusit', 'unknown']
_YES_NO_OUTPUTS = ['ano', 'nie', 'unknown']
_ATTACHMENT_ROUTE_CHOICE_OUTPUTS = ['create_contact', 'save_contract', 'cancel', 'unknown']
_ATTACHMENT_DOCUMENT_TYPE_CHOICE_OUTPUTS = [
    'receipt',
    'incoming_invoice',
    'contract',
    'contact_source',
    'cancel',
    'unknown',
]
_GLOBAL_CANCEL_OUTPUTS = ['cancel', 'unknown']
_GLOBAL_CANCEL_SHORTCUTS = {
    'cancel',
    'zrusit',
    'skoncit',
    'spat',
    'naspat',
    'скасувати',
    'відмінити',
    'відминити',
    'отменить',
    'почни з початку',
    'почати з початку',
    'начать сначала',
}

_APPROVE_EDIT_CANCEL_MAP = {
    'schvalit': 'approve',
    'upravit': 'edit',
    'zrusit': 'cancel',
    'unknown': _UNKNOWN,
}
_YES_NO_MAP = {
    'ano': 'yes',
    'nie': 'no',
    'unknown': _UNKNOWN,
}


def _approve_edit_cancel_reply_type(context_name: str) -> str:
    if context_name == 'invoice_postpdf_decision':
        return 'postpdf_decision'
    return 'draft_review_decision'


async def resolve_approve_edit_cancel(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> ApproveEditCancelDecision:
    legacy = await resolve_bounded_confirmation_reply(
        context_name=context_name,
        expected_reply_type=_approve_edit_cancel_reply_type(context_name),
        allowed_outputs=_APPROVE_EDIT_CANCEL_OUTPUTS,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        diagnostics=diagnostics,
    )
    return _APPROVE_EDIT_CANCEL_MAP.get(legacy, _UNKNOWN)


async def resolve_yes_no(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> YesNoDecision:
    legacy = await resolve_bounded_confirmation_reply(
        context_name=context_name,
        expected_reply_type='yes_no_confirmation',
        allowed_outputs=_YES_NO_OUTPUTS,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        diagnostics=diagnostics,
    )
    return _YES_NO_MAP.get(legacy, _UNKNOWN)


async def resolve_attachment_route_choice(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> AttachmentRouteChoiceDecision:
    decision = await resolve_bounded_confirmation_reply(
        context_name=context_name,
        expected_reply_type='attachment_route_choice',
        allowed_outputs=_ATTACHMENT_ROUTE_CHOICE_OUTPUTS,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        diagnostics=diagnostics,
    )
    return decision if decision in _ATTACHMENT_ROUTE_CHOICE_OUTPUTS else _UNKNOWN


async def resolve_attachment_document_type_choice(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> AttachmentDocumentTypeChoiceDecision:
    decision = await resolve_bounded_confirmation_reply(
        context_name=context_name,
        expected_reply_type='attachment_document_type_choice',
        allowed_outputs=_ATTACHMENT_DOCUMENT_TYPE_CHOICE_OUTPUTS,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        diagnostics=diagnostics,
    )
    return decision if decision in _ATTACHMENT_DOCUMENT_TYPE_CHOICE_OUTPUTS else _UNKNOWN


async def resolve_global_cancel(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> GlobalCancelDecision:
    decision = await resolve_bounded_confirmation_reply(
        context_name=context_name,
        expected_reply_type='global_cancel',
        allowed_outputs=_GLOBAL_CANCEL_OUTPUTS,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        diagnostics=diagnostics,
    )
    return decision if decision in _GLOBAL_CANCEL_OUTPUTS else _UNKNOWN


def is_global_cancel_text(user_input_text: str) -> bool:
    return _normalize_text(user_input_text) in {_normalize_text(value) for value in _GLOBAL_CANCEL_SHORTCUTS}


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value.strip().casefold())
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_diacritics).strip()
