from __future__ import annotations

import re
from typing import Any
import unicodedata

from bot.services.semantic_action_resolver import resolve_bounded_confirmation_reply, resolve_semantic_action


ApproveEditCancelDecision = str
YesNoDecision = str
AttachmentRouteChoiceDecision = str
AttachmentDocumentTypeChoiceDecision = str
GlobalCancelDecision = str
ActiveFsmNavigationDecision = str
WorkTimeOpenConflictChoiceDecision = str
WorkTimeMissingDaysChoiceDecision = str
AccountingDocumentCategoryPreviewDecision = str
AccountingDocumentCategoryUnknownDecision = str
AccountingDocumentCategorySelectionDecision = str
AccountingDocumentCategorySimilarDecision = str

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
_ACTIVE_FSM_NAVIGATION_OUTPUTS = [
    'cancel_current_flow',
    'show_main_menu',
    'resume_start_status',
    'pass_through',
]
_WORK_TIME_OPEN_CONFLICT_OUTPUTS = ['close_day', 'fill_time', 'skip_day', 'cancel', 'unknown']
_WORK_TIME_MISSING_DAYS_OUTPUTS = ['fill', 'skip', 'cancel', 'unknown']
_ACCOUNTING_CATEGORY_PREVIEW_OUTPUTS = [
    'save_with_category',
    'change_document_category',
    'change_line_item_category',
    'save_without_category',
    'cancel',
    'unknown',
]
_ACCOUNTING_CATEGORY_UNKNOWN_OUTPUTS = [
    'choose_existing_category',
    'create_new_category',
    'save_as_unknown_review',
    'cancel',
    'unknown',
]
_ACCOUNTING_CATEGORY_SIMILAR_OUTPUTS = [
    'use_existing_category',
    'create_new_anyway',
    'back',
    'unknown',
]
_GLOBAL_CANCEL_SHORTCUTS = {
    'cancel',
    'zrusit',
    'skoncit',
    'spat',
    'naspat',
    'назад',
    'скасувати',
    'відмінити',
    'відминити',
    'отменить',
    'почни з початку',
    'почати з початку',
    'начать сначала',
}

_ACTIVE_FSM_NAVIGATION_SHORTCUTS = {
    'cancel_current_flow': {
        'cancel',
        'zrusit',
        'skoncit',
        'spat',
        'naspat',
        'скасувати',
        'відмінити',
        'отменить',
    },
    'show_main_menu': {
        'menu',
        'hlavne menu',
        'hlavny zoznam',
        'ukaz menu',
        'zobraz menu',
        'меню',
        'головне меню',
        'главное меню',
    },
    'resume_start_status': {
        'start',
        'zacat',
        'zacat odznova',
        'spustit znova',
        'start over',
        'почати',
        'почати спочатку',
        'почни з початку',
        'начать',
        'начать сначала',
    },
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
    normalized = _normalize_text(user_input_text)
    if context_name == 'accounting_document_duplicate_save_decision':
        if 'ulozit aj tak' in normalized or 'save anyway' in normalized:
            return 'yes'
        if 'pridat iny blocek' in normalized or 'pridat iny' in normalized or 'add another receipt' in normalized or normalized == 'menu':
            return 'no'
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


async def resolve_active_fsm_navigation(
    *,
    context_name: str,
    user_input_text: str,
    current_state: str | None,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> ActiveFsmNavigationDecision:
    normalized = _normalize_text(user_input_text)
    for decision, shortcuts in _ACTIVE_FSM_NAVIGATION_SHORTCUTS.items():
        if normalized in {_normalize_text(value) for value in shortcuts}:
            return decision

    decision = await resolve_semantic_action(
        context_name=context_name,
        allowed_actions=_ACTIVE_FSM_NAVIGATION_OUTPUTS,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        auxiliary_context={
            'current_state': current_state,
            'state_scope': 'active_fsm_navigation_interrupt',
            'supported_languages': ['sk', 'uk', 'ru'],
            'failure_mode': 'pass_through_for_fresh_updates',
            **(diagnostics or {}),
        },
        action_hints={
            'cancel_current_flow': {
                'meaning': 'the user wants to abandon the current unfinished FSM action only',
                'not_this': ['approval, save, send, pay, mark-paid, or edit-current-preview intent'],
            },
            'show_main_menu': {
                'meaning': 'the user wants the existing main menu or list of available bot actions',
                'not_this': ['creating an invoice, choosing a category, approving a preview'],
            },
            'resume_start_status': {
                'meaning': 'the user wants to restart from the existing /start staged setup/status router',
                'not_this': ['approve current preview, edit current draft, enter a date/time/value'],
            },
            'pass_through': {
                'meaning': (
                    'ordinary state-owned input, approval/edit/yes/no, time, date, category, '
                    'document answer, or business value that the active FSM handler must process unchanged'
                ),
            },
        },
    )
    return decision if decision in _ACTIVE_FSM_NAVIGATION_OUTPUTS else 'pass_through'
async def resolve_accounting_document_category_preview_decision(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> AccountingDocumentCategoryPreviewDecision:
    normalized = _normalize_text(user_input_text)
    decision = _resolve_accounting_category_preview_fallback(normalized)
    if decision != _UNKNOWN:
        return decision
    legacy = await resolve_approve_edit_cancel(
        context_name=context_name,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        diagnostics=diagnostics,
    )
    return {
        'approve': 'save_with_category',
        'edit': 'change_document_category',
        'cancel': 'cancel',
        'unknown': _UNKNOWN,
    }.get(legacy, _UNKNOWN)


async def resolve_accounting_document_category_unknown_decision(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> AccountingDocumentCategoryUnknownDecision:
    del context_name, api_key, model, diagnostics
    normalized = _normalize_text(user_input_text)
    if not normalized:
        return _UNKNOWN
    if 'existuj' in normalized or 'vybrat' in normalized or 'zvolit' in normalized or 'choose' in normalized:
        return 'choose_existing_category'
    if 'vytvor' in normalized or 'nova' in normalized or 'novu' in normalized or 'create' in normalized:
        return 'create_new_category'
    if 'kontrol' in normalized or 'unknown' in normalized or 'bez kategorie' in normalized:
        return 'save_as_unknown_review'
    if normalized in {'zrusit', 'cancel', 'nie', 'no', 'spat', 'naspat'}:
        return 'cancel'
    return _UNKNOWN


async def resolve_accounting_document_category_selection(
    *,
    context_name: str,
    user_input_text: str,
    allowed_categories: list[dict[str, Any]],
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> AccountingDocumentCategorySelectionDecision:
    del context_name, api_key, model, diagnostics
    normalized = _normalize_text(user_input_text)
    if not normalized:
        return _UNKNOWN
    if 'vytvor' in normalized or 'create new categor' in normalized:
        return 'create_new_category'
    if normalized in {'spat', 'naspat', 'back'}:
        return 'back'
    if normalized in {'zrusit', 'cancel'}:
        return 'cancel'
    for category in allowed_categories:
        category_id = str(category.get('category_id') or '').strip()
        label = str(category.get('label_sk') or '').strip()
        if normalized == _normalize_text(category_id) or normalized == _normalize_text(label):
            return category_id
    return _UNKNOWN


async def resolve_accounting_document_category_similar_decision(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> AccountingDocumentCategorySimilarDecision:
    del context_name, api_key, model, diagnostics
    normalized = _normalize_text(user_input_text)
    if 'existuj' in normalized or 'pouzit' in normalized or 'pouzije' in normalized or 'use' in normalized:
        return 'use_existing_category'
    if 'aj tak' in normalized or 'vytvor' in normalized or 'create' in normalized:
        return 'create_new_anyway'
    if normalized in {'spat', 'naspat', 'zrusit', 'cancel', 'nie', 'no'}:
        return 'back'
    return _UNKNOWN



async def resolve_work_time_open_conflict_choice(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> WorkTimeOpenConflictChoiceDecision:
    del context_name, api_key, model, diagnostics
    normalized = _normalize_text(user_input_text)
    if not normalized:
        return _UNKNOWN
    if 'uzav' in normalized or 'zatvor' in normalized or 'close' in normalized:
        return 'close_day'
    if 'dopln' in normalized or 'vypln' in normalized or 'fill' in normalized:
        return 'fill_time'
    if 'preskoc' in normalized or 'skip' in normalized:
        return 'skip_day'
    if normalized in {'zrusit', 'cancel', 'spat', 'naspat', 'nie', 'no'}:
        return 'cancel'
    return _UNKNOWN


async def resolve_work_time_missing_days_choice(
    *,
    context_name: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> WorkTimeMissingDaysChoiceDecision:
    del context_name, api_key, model, diagnostics
    normalized = _normalize_text(user_input_text)
    if not normalized:
        return _UNKNOWN
    if 'dopln' in normalized or 'vypln' in normalized or 'fill' in normalized:
        return 'fill'
    if 'preskoc' in normalized or 'skip' in normalized:
        return 'skip'
    if normalized in {'zrusit', 'cancel', 'spat', 'naspat', 'nie', 'no'}:
        return 'cancel'
    return _UNKNOWN
def is_global_cancel_text(user_input_text: str) -> bool:
    return _normalize_text(user_input_text) in {_normalize_text(value) for value in _GLOBAL_CANCEL_SHORTCUTS}


def _resolve_accounting_category_preview_fallback(normalized: str) -> str:
    if not normalized:
        return _UNKNOWN
    if normalized in {'zrusit', 'cancel', 'nie', 'no'}:
        return 'cancel'
    if 'bez kategor' in normalized:
        return 'save_without_category'
    if 'polozk' in normalized and ('zmen' in normalized or 'upravit' in normalized or 'kategor' in normalized):
        return 'change_line_item_category'
    if 'hlavn' in normalized and 'kategor' in normalized:
        return 'change_document_category'
    if 'zmen' in normalized and 'kategor' in normalized:
        return 'change_document_category'
    if normalized in {'upravit', 'edit', 'opravit'}:
        return 'change_document_category'
    if normalized in {'ulozit s kategoriou', 'ulozit kategorie', 'ulozit', 'schvalit', 'potvrdit', 'ano', 'ok', 'tak'}:
        return 'save_with_category'
    return _UNKNOWN


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value.strip().casefold())
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    without_button_prefix = re.sub(r'^[^\w]+', '', without_diacritics).strip()
    return re.sub(r'\s+', ' ', without_button_prefix).strip()
