from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from openai import AsyncOpenAI


_UNKNOWN = 'unknown'


def _tokenize(value: str) -> set[str]:
    tokens = {token for token in re.findall(r'[^\W\d_]+', value.lower(), flags=re.UNICODE) if token}
    normalized: set[str] = set()
    for token in tokens:
        norm = unicodedata.normalize('NFKD', token)
        normalized.add(''.join(ch for ch in norm if not unicodedata.combining(ch)))
    return normalized


def _fallback_for_context(context_name: str, text: str, allowed: set[str]) -> str:
    tokens = _tokenize(text)
    if not tokens:
        return _UNKNOWN

    if context_name == 'top_level_action':
        create_invoice_triggers = {
            'fakturu',
            'faktura',
            'faktury',
            'фактуру',
            'invoice',
            'vytvor',
            'sprav',
            'urob',
            'zrob',
            'сделай',
            'витворить',
            'створи',
        }
        add_contact_verbs = {
            'pridaj',
            'dodaj',
            'add',
            'uloz',
            'ulozit',
            'save',
            'додай',
            'добавь',
            'добавить',
        }
        add_contact_targets = {'kontakt', 'контакт', 'контрагента', 'firmu', 'company', 'spolocnost', 'контрагент'}

        if 'send_invoice' in allowed and tokens.intersection({'posli', 'send', 'відправ', 'отправь'}):
            return 'send_invoice'
        if 'edit_invoice' in allowed and tokens.intersection({'upravit', 'редагувати', 'исправь', 'изменить'}):
            return 'edit_invoice'
        if 'create_invoice' in allowed and tokens.intersection(create_invoice_triggers):
            return 'create_invoice'
        if 'add_contact' in allowed and tokens.intersection(add_contact_verbs) and tokens.intersection(add_contact_targets):
            return 'add_contact'
        return _UNKNOWN

    if context_name == 'invoice_preview_confirmation':
        if 'ano' in allowed and tokens.intersection(
            {'ano', 'tak', 'так', 'да', 'добре', 'ok', 'yes', 'potvrdzujem'}
        ):
            return 'ano'
        if 'nie' in allowed and tokens.intersection({'nie', 'ні', 'нет', 'cancel', 'nechcem', 'no'}):
            return 'nie'
        return _UNKNOWN

    if context_name == 'invoice_postpdf_decision':
        if 'schvalit' in allowed and tokens.intersection(
            {'schvalit', 'подтвердить', 'схвалити', 'approve', 'да', 'так', 'potvrdit'}
        ):
            return 'schvalit'
        if 'upravit' in allowed and tokens.intersection(
            {'upravit', 'редагувати', 'зміни', 'изменить', 'исправить', 'управить'}
        ):
            return 'upravit'
        if 'zrusit' in allowed and tokens.intersection(
            {
                'zrusit',
                'видалити',
                'удалить',
                'delete',
                'отменить',
                'скасувати',
                'знищити',
                'зрушити',
                'зрушить',
                'нет',
                'ні',
                'nie',
            }
        ):
            return 'zrusit'
        return _UNKNOWN

    if context_name == 'contact_confirm':
        if 'ano' in allowed and tokens.intersection({'ano', 'áno', 'tak', 'yes', 'да'}):
            return 'ano'
        if 'nie' in allowed and tokens.intersection({'nie', 'ні', 'нет', 'no', 'cancel'}):
            return 'nie'
        return _UNKNOWN

    return _UNKNOWN


async def resolve_semantic_action(
    *,
    context_name: str,
    allowed_actions: list[str],
    user_input_text: str,
    api_key: str | None,
    model: str,
    auxiliary_context: dict[str, Any] | None = None,
) -> str:
    allowed = {value.strip() for value in allowed_actions if value and value.strip()}
    if _UNKNOWN not in allowed:
        allowed.add(_UNKNOWN)

    cleaned = user_input_text.strip()
    if not cleaned:
        return _UNKNOWN

    if api_key and api_key.startswith('sk-'):
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a bounded semantic canonicalizer. '
                            'Return JSON only: {"canonical_action":"..."} where value is one allowed action or "unknown". '
                            'Never return explanations.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': context_name,
                                'allowed_actions': sorted(allowed),
                                'user_input_text': cleaned,
                                'auxiliary_context': auxiliary_context or {},
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            parsed = json.loads(raw)
            canonical = str(parsed.get('canonical_action', _UNKNOWN)).strip()
            if canonical in allowed:
                return canonical
        except Exception:
            pass

    return _fallback_for_context(context_name, cleaned, allowed)


async def resolve_semantic_value(
    *,
    context_name: str,
    allowed_values: list[str],
    user_input_text: str,
    api_key: str | None,
    model: str,
    auxiliary_context: dict[str, Any] | None = None,
) -> str:
    return await resolve_semantic_action(
        context_name=context_name,
        allowed_actions=allowed_values,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        auxiliary_context=auxiliary_context,
    )
