from __future__ import annotations

import asyncio
from difflib import get_close_matches
import json
from typing import Any

from openai import AsyncOpenAI

from bot.services.info_help import (
    ALLOWED_ADMIN_REVIEW_DRAFT_DOMAINS,
    ALLOWED_ADMIN_REVIEW_RISK_LEVELS,
    ALLOWED_INFO_HELP_TOPIC_IDS,
    ALLOWED_INFO_HELP_TRIAGE_CLASSES,
    InfoHelpTriageResult,
    parse_info_help_triage_model_output,
)
from bot.services.info_help_action_registry import info_help_action_payload
from bot.services.info_help_assistant import (
    KNOWN_INFO_HELP_COMMANDS,
    InfoHelpAssistantResult,
    build_info_help_product_truth_view,
    parse_info_help_assistant_model_output,
)
from bot.services.product_truth import list_capabilities


def build_info_help_assistant_payload(
    *,
    current_input_text: str,
    input_channel: str,
    primary_resolver_result: str,
    primary_resolver_diagnostics: dict[str, Any] | None = None,
    primary_mutation_class: str = 'informational',
    recent_conversation: tuple[dict[str, object], ...] | list[dict[str, object]] = (),
    explicit_reply: dict[str, object] | None = None,
    active_runtime_context: dict[str, object] | None = None,
    known_command_tokens: tuple[str, ...] | list[str] = KNOWN_INFO_HELP_COMMANDS,
) -> dict[str, Any]:
    cleaned = ' '.join(current_input_text.split())[:1200]
    raw_command = cleaned.split(maxsplit=1)[0] if cleaned.startswith('/') else None
    return {
        'context_name': 'info_help_contextual_assistant_v2',
        'current_input': {
            'current_input_text': cleaned,
            'normalized_input_text': cleaned.casefold(),
            'input_channel': input_channel if input_channel in {'text', 'command', 'voice_stt'} else 'text',
            'likely_language': _likely_language(cleaned),
            'raw_slash_command_token': raw_command,
            'normalized_slash_command_token': raw_command.casefold() if raw_command else None,
            'nearest_known_command_hints': (
                get_close_matches(raw_command.casefold(), list(known_command_tokens), n=3, cutoff=0.55)
                if raw_command else []
            ),
            'primary_resolver_result': primary_resolver_result,
            'primary_resolver_diagnostics': primary_resolver_diagnostics or {},
            'primary_mutation_class': primary_mutation_class,
            'appears_noisy_or_malformed': len(cleaned) < 2,
        },
        'explicit_telegram_reply': explicit_reply,
        'recent_conversation': list(recent_conversation)[:6],
        'active_runtime_context': active_runtime_context or {},
        'product_and_action_context': {
            'product_truth': build_info_help_product_truth_view(),
            'canonical_actions': info_help_action_payload(),
            'known_command_tokens': list(known_command_tokens),
            'negative_space': [
                'receipt/delete is not invoice/delete',
                'contact/edit is not supplier_profile/edit',
                'capability questions never execute',
                'vague destructive requests never execute',
                'account-wide deletion is never suggested by InfoHelp',
            ],
        },
        'expected_output': {
            'intent_kind': 'one bounded intent kind',
            'speech_act': 'one bounded speech act',
            'domain_id': 'one bounded domain or unknown',
            'object_kind': 'one bounded object or unknown',
            'operation_id': 'one bounded operation or unknown',
            'target_reference': 'bounded string or null',
            'proposed_action_id': 'provided action or null',
            'proposed_capability_id': 'provided capability or null',
            'probable_command_target': 'provided command or null',
            'intent_complete': 'boolean',
            'missing_slots': 'bounded slot list',
            'is_correction': 'boolean',
            'negated_objects': 'bounded object list',
            'negated_operations': 'bounded operation list',
            'corrected_from_object': 'bounded object or null',
            'corrected_to_object': 'bounded object or null',
            'refers_to_active_flow': 'boolean',
            'refers_to_explicit_reply': 'boolean',
            'confidence': '0..1',
            'acknowledgement_sk': 'short non-factual Slovak acknowledgement',
            'clarification_question_sk': 'short Slovak question or empty',
        },
    }


async def resolve_info_help_assistant_with_llm(
    *,
    current_input_text: str,
    api_key: str | None,
    model: str,
    input_channel: str,
    primary_resolver_result: str,
    primary_resolver_diagnostics: dict[str, Any] | None = None,
    primary_mutation_class: str = 'informational',
    recent_conversation: tuple[dict[str, object], ...] | list[dict[str, object]] = (),
    explicit_reply: dict[str, object] | None = None,
    active_runtime_context: dict[str, object] | None = None,
    timeout_seconds: float = 8.0,
) -> InfoHelpAssistantResult:
    """Run exactly one enhanced InfoHelp call; no retries or secondary classifier."""
    cleaned = current_input_text.strip()
    if not cleaned or not api_key or not api_key.startswith('sk-'):
        return InfoHelpAssistantResult()
    payload = build_info_help_assistant_payload(
        current_input_text=cleaned,
        input_channel=input_channel,
        primary_resolver_result=primary_resolver_result,
        primary_resolver_diagnostics=primary_resolver_diagnostics,
        primary_mutation_class=primary_mutation_class,
        recent_conversation=recent_conversation,
        explicit_reply=explicit_reply,
        active_runtime_context=active_runtime_context,
    )
    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are the single bounded contextual InfoHelp assistant for OfficeFlow/FakturaBot. '
                            'Return JSON only in the provided schema. Extract exact domain, object, operation, speech act, '
                            'correction, negation, references and missing slots. Select only provided IDs. Different business '
                            'objects are never interchangeable because verbs are similar. Capability questions never execute. '
                            'Do not return Product Truth status, callback data, side effects, SQL, handler paths, or claims '
                            'that data changed.'
                        ),
                    },
                    {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
                ],
            ),
            timeout=timeout_seconds,
        )
    except Exception:
        return InfoHelpAssistantResult()
    return parse_info_help_assistant_model_output(response.choices[0].message.content or '{}')


def _likely_language(value: str) -> str:
    lowered = value.casefold()
    if any(char in lowered for char in 'іїєґ'):
        return 'uk'
    if any(char in lowered for char in 'ыэъё'):
        return 'ru'
    if any(char in lowered for char in 'čďľĺňóôŕšťúýžáäéí'):
        return 'sk'
    if any('\u0400' <= char <= '\u04ff' for char in lowered):
        return 'mixed'
    return 'unknown'


_SUPPORTED_LANGUAGES = ('sk', 'uk', 'ru', 'mixed')
_CONTEXT_NAME = 'info_help_triage'


def build_info_help_triage_payload(
    *,
    user_input_text: str,
    input_channel: str = 'text',
    current_state: str | None = None,
) -> dict[str, Any]:
    """Build the bounded Python-to-LLM payload for InfoHelp/Triage classification."""
    return {
        'context_name': _CONTEXT_NAME,
        'current_state': current_state,
        'input_channel': input_channel if input_channel in {'text', 'voice'} else 'text',
        'user_input_text': user_input_text,
        'supported_languages': list(_SUPPORTED_LANGUAGES),
        'known_capabilities': [
            {
                'capability_id': capability.capability_id,
                'title': capability.title,
                'domain': capability.domain,
                'classification_summary': _classification_summary(capability.title, capability.domain),
            }
            for capability in list_capabilities()
        ],
        'allowed_topic_ids': list(ALLOWED_INFO_HELP_TOPIC_IDS),
        'allowed_triage_classes': list(ALLOWED_INFO_HELP_TRIAGE_CLASSES),
        'request_storage_available': True,
        'admin_notification_available': False,
        'allowed_admin_review_domains': list(ALLOWED_ADMIN_REVIEW_DRAFT_DOMAINS),
        'allowed_risk_levels': list(ALLOWED_ADMIN_REVIEW_RISK_LEVELS),
        'product_context': (
            'OfficeFlow/FakturaBot is an AI-assisted business operating layer for invoices, '
            'contacts, supplier/business profiles, accounting documents, work time, reports, '
            'workspace setup, and account-specific business workflows. Telegram is only the UI.'
        ),
        'unknown_product_truth_policy': (
            'If no known Product Truth capability answers a business-domain question, classify it as '
            'new_business_feature_request, customization_request_candidate, admin_review_candidate, '
            'or possible_product_truth_candidate when safe. Use unknown only for genuinely unclear input.'
        ),
        'expected_output': {
            'capability_id': 'known capability_id or unknown',
            'topic_id': 'one allowed topic_id',
            'triage_class': 'one allowed triage_class',
            'confidence': 'number from 0 to 1',
            'needs_clarification': 'boolean',
            'admin_review_draft': {
                'business_need': 'Slovak business wording of what the user wants, empty unless request/review candidate',
                'detected_domain': 'one allowed_admin_review_domains value',
                'expected_outcome': 'Slovak business wording of what the user expects or why it matters',
                'clarification_questions': '0-4 short Slovak questions for admin review',
                'proposed_title': 'short Slovak admin-review title',
                'proposed_description': 'structured Slovak admin-review description',
                'risk_level': 'one allowed_risk_levels value',
            },
        },
    }


async def resolve_info_help_triage_with_llm(
    *,
    user_input_text: str,
    api_key: str | None,
    model: str,
    input_channel: str = 'text',
    current_state: str | None = None,
    timeout_seconds: float = 8.0,
) -> InfoHelpTriageResult:
    """Classify InfoHelp/Triage input via LLM, then validate through the existing parser."""
    cleaned = user_input_text.strip()
    if not cleaned or not api_key or not api_key.startswith('sk-'):
        return InfoHelpTriageResult()

    payload = build_info_help_triage_payload(
        user_input_text=cleaned,
        input_channel=input_channel,
        current_state=current_state,
    )
    try:
        client = AsyncOpenAI(api_key=api_key)
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a bounded OfficeFlow/FakturaBot InfoHelp classifier. '
                            'Return JSON only with capability_id, topic_id, triage_class, confidence, '
                            'needs_clarification, and optional admin_review_draft for request/review candidates. '
                            'Classify user input into Python-provided capability IDs, topic IDs, and triage classes only. '
                            'Never return answer text, response modes, support status, canonical actions, '
                            'admin messages, side effects, or Product Truth facts. '
                            'For safe business-domain requests not covered by Product Truth, draft only structured admin-review metadata. '
                            'All free-text fields inside admin_review_draft must be Slovak business wording, even when the user input is English, Ukrainian, Russian, mixed, or STT-noisy. '
                            'Prefer request/review triage classes over unknown for OfficeFlow business needs such as multiple profiles, '
                            'workspace switching, custom reports, delivery/storage/integration wishes, or account-specific workflows. '
                            'If no provided capability or triage class safely fits, return unknown. '
                            'User input may be Slovak, Ukrainian, Russian, mixed-language, colloquial, or STT-noisy.'
                        ),
                    },
                    {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
                ],
            ),
            timeout=timeout_seconds,
        )
    except Exception:
        return InfoHelpTriageResult()

    raw = response.choices[0].message.content or '{}'
    return parse_info_help_triage_model_output(raw)


def _classification_summary(title: str, domain: str) -> str:
    return (
        f'Use this capability only when the user asks about the OfficeFlow/FakturaBot product area '
        f'named "{title}" in domain "{domain}". This is classification metadata only, not support status.'
    )
