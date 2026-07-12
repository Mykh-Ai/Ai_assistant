from __future__ import annotations

import asyncio
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
from bot.services.product_truth import list_capabilities


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
