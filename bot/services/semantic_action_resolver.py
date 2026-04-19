from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

from openai import AsyncOpenAI


_UNKNOWN = 'unknown'
_QUANTITY_UNIT_PRICE_CANONICAL = 'quantity_unit_price_pair'
_SUPPORTED_CONFIRM_LANGUAGES = ['sk', 'uk', 'ru']
logger = logging.getLogger(__name__)


def _tokenize(value: str) -> set[str]:
    tokens = {token for token in re.findall(r'[^\W\d_]+', value.lower(), flags=re.UNICODE) if token}
    normalized: set[str] = set()
    for token in tokens:
        norm = unicodedata.normalize('NFKD', token)
        normalized.add(''.join(ch for ch in norm if not unicodedata.combining(ch)))
    return normalized


def _fallback_for_context(context_name: str, text: str, allowed: set[str]) -> str:
    tokens = _tokenize(text)
    if context_name == 'invoice_edit_item_target_selection':
        numeric_match = re.search(r'\b(\d+)\b', text)
        if numeric_match:
            numeric_value = numeric_match.group(1)
            if numeric_value in allowed:
                return numeric_value
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
        add_service_alias_verbs = {
            'pridaj',
            'dodaj',
            'add',
            'создай',
            'додай',
            'добавь',
            'predaj',
            'предай',
        }
        add_service_alias_targets = {
            'sluzbu',
            'sluzba',
            'polozku',
            'polozka',
            'службу',
            'положку',
            'живность',
            'item',
            'service',
        }

        if 'send_invoice' in allowed and tokens.intersection({'posli', 'send', 'відправ', 'отправь'}):
            return 'send_invoice'
        if 'edit_invoice' in allowed and tokens.intersection({'upravit', 'редагувати', 'исправь', 'изменить'}):
            return 'edit_invoice'
        if 'create_invoice' in allowed and tokens.intersection(create_invoice_triggers):
            return 'create_invoice'
        if 'add_contact' in allowed and tokens.intersection(add_contact_verbs) and tokens.intersection(add_contact_targets):
            return 'add_contact'
        if 'add_service_alias' in allowed and tokens.intersection(add_service_alias_verbs) and tokens.intersection(
            add_service_alias_targets
        ):
            return 'add_service_alias'
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

    if context_name == 'invoice_edit_scope_selection':
        if 'invoice_level' in allowed and tokens.intersection({'faktura', 'faktúra', 'invoice', 'cislo', 'číslo', 'datum', 'dátum'}):
            return 'invoice_level'
        if 'item_level' in allowed and tokens.intersection({'polozka', 'položka', 'sluzba', 'služba', 'opis', 'detail'}):
            return 'item_level'
        return _UNKNOWN

    if context_name == 'invoice_edit_invoice_action':
        if 'edit_invoice_number' in allowed and tokens.intersection({'cislo', 'číslo', 'number', 'num'}):
            return 'edit_invoice_number'
        if 'edit_invoice_issue_date' in allowed and tokens.intersection({'vystavenia', 'vystavenie', 'issue'}):
            return 'edit_invoice_issue_date'
        if 'edit_invoice_delivery_date' in allowed and tokens.intersection({'dodania', 'dodanie', 'delivery'}):
            return 'edit_invoice_delivery_date'
        if 'edit_invoice_due_date' in allowed and tokens.intersection({'splatnosti', 'splatnost', 'due'}):
            return 'edit_invoice_due_date'
        if 'edit_invoice_date' in allowed and tokens.intersection({'datum', 'dátum', 'date'}):
            return 'edit_invoice_date'
        return _UNKNOWN

    if context_name == 'invoice_edit_item_target_selection':
        ordered_candidates = [
            ('1', {'1', 'prva', 'prvá', 'prvy', 'prvý', 'jedna', 'jeden'}),
            ('2', {'2', 'druha', 'druhá', 'druhy', 'druhý', 'dva', 'dve'}),
            ('3', {'3', 'tretia', 'treti', 'tretí', 'tri'}),
        ]
        for canonical_index, hint_tokens in ordered_candidates:
            if canonical_index in allowed and tokens.intersection(hint_tokens):
                return canonical_index
        return _UNKNOWN

    if context_name == 'invoice_edit_item_action':
        if 'clear_item_details' in allowed and tokens.intersection(
            {'vymazat', 'vymazať', 'zmazat', 'zmazať', 'odstranit', 'odstrániť', 'clear', 'delete'}
        ) and tokens.intersection({'detail', 'detaily', 'details', 'poznamka', 'poznámka'}):
            return 'clear_item_details'
        if 'add_item_details' in allowed and tokens.intersection(
            {'pridat', 'pridať', 'doplnit', 'doplniť', 'add'}
        ) and tokens.intersection({'detail', 'detaily', 'details', 'poznamka', 'poznámka'}):
            return 'add_item_details'
        if 'replace_main_description' in allowed and tokens.intersection(
            {'novy', 'nový', 'opis', 'popis', 'description'}
        ):
            return 'replace_main_description'
        if 'replace_service' in allowed and tokens.intersection(
            {'sluzba', 'služba', 'sluzbu', 'službu', 'service', 'polozka', 'položka', 'polozku', 'položku'}
        ):
            return 'replace_service'
        if 'add_item_details' in allowed and tokens.intersection({'detail', 'detaily', 'details', 'poznamka', 'poznámka'}):
            return 'add_item_details'
        return _UNKNOWN

    return _UNKNOWN


def _normalize_bounded_reply_text(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r'[^\w\s\u0400-\u04FF-]', ' ', cleaned, flags=re.UNICODE)
    cleaned = ' '.join(cleaned.split())
    if not cleaned:
        return ''
    normalized = unicodedata.normalize('NFKD', cleaned)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def _fallback_bounded_confirmation_reply(
    *,
    context_name: str,
    expected_reply_type: str,
    text: str,
    allowed_outputs: set[str],
) -> str:
    normalized = _normalize_bounded_reply_text(text)
    if not normalized:
        return _UNKNOWN

    if context_name == 'invoice_preview_confirmation' and expected_reply_type == 'yes_no_confirmation':
        positive = {'ano', 'tak', 'da', 'так', 'да'}
        negative = {'nie', 'net', 'ні', 'нет'}
        if normalized in positive and 'ano' in allowed_outputs:
            return 'ano'
        if normalized in negative and 'nie' in allowed_outputs:
            return 'nie'
        return _UNKNOWN

    if context_name == 'contact_confirm' and expected_reply_type == 'yes_no_confirmation':
        positive = {'ano', 'tak', 'da', 'так', 'да'}
        negative = {'nie', 'net', 'ні', 'нет'}
        if normalized in positive and 'ano' in allowed_outputs:
            return 'ano'
        if normalized in negative and 'nie' in allowed_outputs:
            return 'nie'
        return _UNKNOWN

    if context_name == 'invoice_postpdf_decision' and expected_reply_type == 'postpdf_decision':
        approve_values = {'schvalit', 'potvrdit', 'схвалити', 'подтвердить'}
        edit_values = {'upravit', 'изменить', 'исправить', 'редагувати', 'зміни'}
        cancel_values = {'zrusit', 'отменить', 'скасувати', 'нет', 'ні', 'nie'}

        if normalized in approve_values and 'schvalit' in allowed_outputs:
            return 'schvalit'
        if normalized in edit_values and 'upravit' in allowed_outputs:
            return 'upravit'
        if normalized in cancel_values and 'zrusit' in allowed_outputs:
            return 'zrusit'
        return _UNKNOWN

    return _UNKNOWN


_NUMBER_WORDS_TO_FLOAT = {
    'jeden': 1.0,
    'jedna': 1.0,
    'jedno': 1.0,
    'raz': 1.0,
    'один': 1.0,
    'одна': 1.0,
    'одно': 1.0,
    'два': 2.0,
    'две': 2.0,
    'дві': 2.0,
    'dva': 2.0,
    'dve': 2.0,
    'tri': 3.0,
    'три': 3.0,
    'styri': 4.0,
    'štyri': 4.0,
    'четыре': 4.0,
    'чотири': 4.0,
}

_QTY_TOKEN_PATTERN = (
    r'\d+(?:[.,]\d+)?|'
    r'jeden|jedna|jedno|raz|dva|dve|tri|styri|štyri|'
    r'один|одна|одно|два|две|дві|три|четыре|чотири'
)
_PRICE_NUMBER_PATTERN = r'\d+(?:[.,]\d+)?'
_PAIR_SPACED_PATTERN = re.compile(
    rf'^\s*(?P<qty>{_QTY_TOKEN_PATTERN})\s+(?P<unit>{_PRICE_NUMBER_PATTERN})\s*$',
    flags=re.IGNORECASE,
)
_PAIR_MULTIPLIER_PATTERN = re.compile(
    rf'^\s*(?P<qty>{_QTY_TOKEN_PATTERN})\s*(?:\*|x|kr[aá]t|крат|razi|razy|раз|раза|рази|kusy|kus|ks)?\s*(?:po|по)?\s*(?P<unit>{_PRICE_NUMBER_PATTERN})\s*$',
    flags=re.IGNORECASE,
)
_PAIR_LABELED_PATTERN = re.compile(
    rf'^\s*(?:mno[zž]stvo|koli[cč]estvo|количество)\s*(?P<qty>{_QTY_TOKEN_PATTERN})\s*[,;]?\s*(?:cena(?:\s+za\s+(?:kus|ks|jednotku))?|цена(?:\s+за\s+(?:штуку|единицу|ед))?)\s*(?P<unit>{_PRICE_NUMBER_PATTERN})\s*$',
    flags=re.IGNORECASE,
)
_SINGLE_PRICE_PATTERN = re.compile(r'^\s*(?P<unit>\d+(?:[.,]\d+)?)\s*$')


def _parse_positive_float(value: str) -> float | None:
    try:
        parsed = float(value.replace(',', '.').strip())
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _parse_quantity_token(value: str) -> float | None:
    parsed = _parse_positive_float(value)
    if parsed is not None:
        return parsed
    return _NUMBER_WORDS_TO_FLOAT.get(value.strip().lower())


def _fallback_quantity_unit_price_pair(text: str) -> tuple[float, float] | None:
    normalized_text = text.strip()
    if not normalized_text:
        return None

    for pattern in (_PAIR_SPACED_PATTERN, _PAIR_MULTIPLIER_PATTERN, _PAIR_LABELED_PATTERN):
        match = pattern.match(normalized_text)
        if not match:
            continue
        quantity = _parse_quantity_token(match.group('qty'))
        unit_price = _parse_positive_float(match.group('unit'))
        if quantity is not None and unit_price is not None:
            return quantity, unit_price

    single_match = _SINGLE_PRICE_PATTERN.match(normalized_text)
    if single_match:
        unit_price = _parse_positive_float(single_match.group('unit'))
        if unit_price is not None:
            return 1.0, unit_price

    return None


async def resolve_semantic_action(
    *,
    context_name: str,
    allowed_actions: list[str],
    user_input_text: str,
    api_key: str | None,
    model: str,
    auxiliary_context: dict[str, Any] | None = None,
    action_hints: dict[str, Any] | None = None,
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
                                'current_state': auxiliary_context.get('current_state') if isinstance(auxiliary_context, dict) else None,
                                'supported_languages': _SUPPORTED_CONFIRM_LANGUAGES,
                                'allowed_actions': sorted(allowed),
                                'user_input_text': cleaned,
                                'expected_output': {'canonical_action': 'one allowed token or unknown'},
                                'auxiliary_context': auxiliary_context or {},
                                'action_hints': action_hints or {},
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


async def resolve_invoice_date_normalization(
    *,
    date_field: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    invoice_context: dict[str, Any] | None = None,
) -> str:
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
                            'You are a bounded normalization engine for invoice date editing. '
                            'Return strict JSON only in format {"normalized_date":"DD.MM.RRRR"} or {"normalized_date":"unknown"}. '
                            'Do not return explanations or extra keys.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': 'invoice_edit_date_value',
                                'date_field': date_field,
                                'required_format': 'DD.MM.RRRR',
                                'allowed_output': ['DD.MM.RRRR', 'unknown'],
                                'normalization_contract': {
                                    'mode': 'bounded_value_normalization',
                                    'do_not_explain': True,
                                    'do_not_return_free_text': True,
                                    'unknown_only_for': ['truly_ambiguous', 'missing_date', 'stt_noise'],
                                },
                                'user_input_text': cleaned,
                                'invoice_context': invoice_context or {},
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            parsed = json.loads(raw)
            normalized = str(parsed.get('normalized_date', _UNKNOWN)).strip()
            if normalized == _UNKNOWN:
                return _UNKNOWN
            if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', normalized):
                return normalized
            return _UNKNOWN
        except Exception:
            logger.exception('Invoice date normalization failed')

    if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', cleaned):
        return cleaned
    return _UNKNOWN


async def resolve_bounded_confirmation_reply(
    *,
    context_name: str,
    expected_reply_type: str,
    allowed_outputs: list[str],
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> str:
    allowed = {value.strip() for value in allowed_outputs if value and value.strip()}
    if _UNKNOWN not in allowed:
        allowed.add(_UNKNOWN)

    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(
            {
                'raw_model_output': None,
                'normalized_output': _UNKNOWN,
                'fallback_used': False,
                'fallback_output': None,
            }
        )

    cleaned = user_input_text.strip()
    if not cleaned:
        if diagnostics is not None:
            diagnostics['fallback_used'] = True
            diagnostics['fallback_output'] = _UNKNOWN
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
                            'You are a bounded intent normalizer for short in-action confirmations/decisions. '
                            'Return JSON only in format {"canonical":"..."} where value is one allowed output token or "unknown". '
                            'Do not return any explanations. '
                            'Reasoning policy: '
                            'Step 1) infer user intent semantically (not literal matching) even if wording is short, multilingual, colloquial, or mildly STT-noisy. '
                            'Step 2) normalize that intent to the allowed canonical token for the current context. '
                            'Step 3) return "unknown" only when intent is truly ambiguous, not a confirmation/decision reply, or genuine STT garbage. '
                            'For expected_reply_type=yes_no_confirmation: user is NOT required to say exact "ano"/"nie"; '
                            'map clear affirmative intent across languages/forms to affirmative canonical output and clear negative intent to negative canonical output. '
                            'For expected_reply_type=postpdf_decision: '
                            'map clear approve/confirm/save-draft intent to schvalit, clear edit/change/correct intent to upravit, '
                            'and clear delete/cancel/remove/discard invoice-draft intent to zrusit, including multilingual/noisy variants. '
                            'Safety rule: do not guess destructive action when intent is unclear; use "unknown" for uncertainty.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': context_name,
                                'expected_reply_type': expected_reply_type,
                                'supported_input_languages': _SUPPORTED_CONFIRM_LANGUAGES,
                                'allowed_canonical_outputs': sorted(allowed),
                                'user_input_text': cleaned,
                                'normalization_contract': {
                                    'mode': 'semantic_intent_first',
                                    'unknown_only_for': [
                                        'true_ambiguity',
                                        'not_a_confirmation_or_decision_reply',
                                        'stt_garbage_or_nonsense',
                                    ],
                                    'context_rules': {
                                        'yes_no_confirmation': {
                                            'affirmative_intent': 'normalize_to_affirmative_token_in_allowed_outputs',
                                            'negative_intent': 'normalize_to_negative_token_in_allowed_outputs',
                                        },
                                        'postpdf_decision': {
                                            'approve_confirm_save_invoice_draft': 'schvalit_if_allowed',
                                            'edit_change_correct_invoice_draft': 'upravit_if_allowed',
                                            'delete_cancel_remove_discard_invoice_draft': 'zrusit_if_allowed',
                                        },
                                    },
                                },
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            if diagnostics is not None:
                diagnostics['raw_model_output'] = raw
            parsed = json.loads(raw)
            canonical = str(parsed.get('canonical', _UNKNOWN)).strip()
            if canonical in allowed:
                if diagnostics is not None:
                    diagnostics['normalized_output'] = canonical
                return canonical
        except Exception:
            logger.exception('Bounded confirmation resolver failed; using fallback')

    fallback_output = _fallback_bounded_confirmation_reply(
        context_name=context_name,
        expected_reply_type=expected_reply_type,
        text=cleaned,
        allowed_outputs=allowed,
    )
    if diagnostics is not None:
        diagnostics['fallback_used'] = True
        diagnostics['fallback_output'] = fallback_output
        diagnostics['normalized_output'] = fallback_output
    return fallback_output


async def resolve_quantity_unit_price_pair(
    *,
    user_input_text: str,
    api_key: str | None,
    model: str,
    clarification_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned = user_input_text.strip()
    if not cleaned:
        return {'canonical': _UNKNOWN}

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
                            'You are a bounded semantic canonicalizer for invoice slot clarification. '
                            'Supported input languages: uk, ru, sk. '
                            'You parse only quantity and unit_price replies. '
                            'Valid inputs are either quantity+unit_price or unit_price-only; '
                            'for unit_price-only set quantity=1. '
                            'Return strict JSON only in one of two shapes: '
                            '{"canonical":"quantity_unit_price_pair","quantity":<number>,"unit_price":<number>} '
                            'or {"canonical":"unknown"}.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': 'invoice_slot_clarification',
                                'expected_reply_type': 'quantity_times_unit_price',
                                'supported_input_languages': ['uk', 'ru', 'sk'],
                                'clarification_context': clarification_context or {},
                                'user_input_text': cleaned,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            parsed = json.loads(raw)
            canonical = str(parsed.get('canonical', _UNKNOWN)).strip()
            if canonical == _QUANTITY_UNIT_PRICE_CANONICAL:
                quantity = _parse_positive_float(str(parsed.get('quantity', '')))
                unit_price = _parse_positive_float(str(parsed.get('unit_price', '')))
                if quantity is not None and unit_price is not None:
                    return {
                        'canonical': _QUANTITY_UNIT_PRICE_CANONICAL,
                        'quantity': quantity,
                        'unit_price': unit_price,
                    }
            if canonical == _UNKNOWN:
                return {'canonical': _UNKNOWN}
        except Exception:
            pass

    fallback = _fallback_quantity_unit_price_pair(cleaned)
    if fallback is None:
        return {'canonical': _UNKNOWN}

    quantity, unit_price = fallback
    return {
        'canonical': _QUANTITY_UNIT_PRICE_CANONICAL,
        'quantity': quantity,
        'unit_price': unit_price,
    }
