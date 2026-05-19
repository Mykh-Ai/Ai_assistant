from __future__ import annotations

import asyncio
import json
from typing import Any

from openai import AsyncOpenAI

from bot.services.info_help import (
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
        'request_storage_available': False,
        'admin_notification_available': False,
        'expected_output': {
            'capability_id': 'known capability_id or unknown',
            'topic_id': 'one allowed topic_id',
            'triage_class': 'one allowed triage_class',
            'confidence': 'number from 0 to 1',
            'needs_clarification': 'boolean',
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
                            'and needs_clarification. '
                            'Classify user input into Python-provided capability IDs, topic IDs, and triage classes only. '
                            'Never return answer text, response modes, support status, canonical actions, request drafts, '
                            'admin messages, side effects, or Product Truth facts. '
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
