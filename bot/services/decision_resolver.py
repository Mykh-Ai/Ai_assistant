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
    if normalized in {'zrusit', 'cancel', 'spat', 'naspat'}:
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
    return re.sub(r'\s+', ' ', without_diacritics).strip()
