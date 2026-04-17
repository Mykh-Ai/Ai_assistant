import json
import re
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI


_PROMPT_PATH = Path(__file__).parent.parent.parent / 'prompts' / 'invoice_draft_prompt.txt'

_REQUIRED_TOP_LEVEL_SECTIONS = {'vstup', 'zamer', 'biznis_sk', 'stopa'}
_REQUIRED_BIZNIS_FIELDS = {
    'odberatel_kandidat',
    'polozka_povodna',
    'termin_sluzby_sk',
    'mnozstvo',
    'jednotka',
    'suma',
    'mena',
    'datum_dodania',
    'splatnost_dni',
    'datum_splatnosti',
}
_OPTIONAL_BIZNIS_FIELDS = {'cena_za_jednotku'}
_MAX_MULTI_ITEMS = 3


class LlmInvoicePayloadError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        partial_payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}
        self.partial_payload = partial_payload


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LlmInvoicePayloadError(f'Invalid LLM payload: {path} must be an object.')
    return value


def _raise_customer_unresolved(
    message: str,
    *,
    candidate: Any,
    payload_snapshot: dict[str, Any] | None,
) -> None:
    raise LlmInvoicePayloadError(
        message,
        error_code='customer_unresolved',
        details={'raw_biznis_sk_odberatel_kandidat': candidate},
        partial_payload=payload_snapshot,
    )


def _validate_lookup_ready_customer_candidate(candidate: Any, *, payload_snapshot: dict[str, Any] | None) -> str:
    if candidate is None or not isinstance(candidate, str):
        _raise_customer_unresolved(
            'Invalid LLM payload: biznis_sk.odberatel_kandidat must be a non-empty lookup-ready string.',
            candidate=candidate,
            payload_snapshot=payload_snapshot,
        )

    value = candidate.strip()
    if not value:
        _raise_customer_unresolved(
            'Invalid LLM payload: biznis_sk.odberatel_kandidat must not be empty/whitespace.',
            candidate=candidate,
            payload_snapshot=payload_snapshot,
        )

    normalized_spaces = re.sub(r'\s+', ' ', value).strip()
    if len(normalized_spaces) > 160:
        _raise_customer_unresolved(
            'Invalid LLM payload: biznis_sk.odberatel_kandidat is too long.',
            candidate=candidate,
            payload_snapshot=payload_snapshot,
        )

    if not re.search(r'[0-9A-Za-zÀ-žЀ-ӿ]', normalized_spaces):
        _raise_customer_unresolved(
            'Invalid LLM payload: biznis_sk.odberatel_kandidat must contain at least one alphanumeric symbol.',
            candidate=candidate,
            payload_snapshot=payload_snapshot,
        )

    return normalized_spaces


def _resolve_service_slots_or_raise(
    *,
    biznis_sk: dict[str, Any],
    payload_snapshot: dict[str, Any],
) -> None:
    polozka_raw = biznis_sk.get('polozka_povodna')
    termin_raw = biznis_sk.get('termin_sluzby_sk')

    if not isinstance(termin_raw, str):
        raise LlmInvoicePayloadError('Invalid LLM payload: biznis_sk.termin_sluzby_sk must be a string or null.')
    termin_normalized = termin_raw.strip()
    if not termin_normalized:
        raise LlmInvoicePayloadError('Invalid LLM payload: biznis_sk.termin_sluzby_sk must not be empty string.')

    if not isinstance(polozka_raw, str) or not polozka_raw.strip():
        polozka_repaired = termin_normalized
    else:
        polozka_repaired = polozka_raw.strip()

    biznis_sk['termin_sluzby_sk'] = termin_normalized
    biznis_sk['polozka_povodna'] = polozka_repaired


def _resolve_service_candidate_or_raise(
    *,
    item_payload: dict[str, Any],
    payload_snapshot: dict[str, Any],
    item_index: int,
) -> None:
    polozka_raw = item_payload.get('polozka_povodna')
    termin_raw = item_payload.get('termin_sluzby_sk')

    if not isinstance(termin_raw, str):
        raise LlmInvoicePayloadError(
            'Invalid LLM payload: biznis_sk.items[].termin_sluzby_sk must be a string.',
            error_code='items_service_unresolved',
            details={'item_index': item_index, 'field': 'termin_sluzby_sk'},
            partial_payload=payload_snapshot,
        )
    termin_normalized = termin_raw.strip()
    if not termin_normalized:
        raise LlmInvoicePayloadError(
            'Invalid LLM payload: biznis_sk.items[].termin_sluzby_sk must not be empty string.',
            error_code='items_service_unresolved',
            details={'item_index': item_index, 'field': 'termin_sluzby_sk'},
            partial_payload=payload_snapshot,
        )

    if not isinstance(polozka_raw, str) or not polozka_raw.strip():
        polozka_repaired = termin_normalized
    else:
        polozka_repaired = polozka_raw.strip()

    item_payload['termin_sluzby_sk'] = termin_normalized
    item_payload['polozka_povodna'] = polozka_repaired


def _validate_optional_items_or_raise(*, biznis_sk: dict[str, Any], payload_snapshot: dict[str, Any]) -> None:
    items_raw = biznis_sk.get('items')
    if items_raw is None:
        return
    if not isinstance(items_raw, list):
        raise LlmInvoicePayloadError(
            'Invalid LLM payload: biznis_sk.items must be an array when present.',
            error_code='items_shape_invalid',
            partial_payload=payload_snapshot,
        )
    if not items_raw:
        raise LlmInvoicePayloadError(
            'Invalid LLM payload: biznis_sk.items must not be empty when present.',
            error_code='items_shape_invalid',
            partial_payload=payload_snapshot,
        )
    if len(items_raw) > _MAX_MULTI_ITEMS:
        raise LlmInvoicePayloadError(
            'Invalid LLM payload: biznis_sk.items exceeds Phase 1 max size.',
            error_code='items_count_exceeded',
            details={'max_items': _MAX_MULTI_ITEMS, 'actual_items': len(items_raw)},
            partial_payload=payload_snapshot,
        )

    normalized_items: list[dict[str, Any]] = []
    for index, raw_item in enumerate(items_raw, start=1):
        if not isinstance(raw_item, dict):
            raise LlmInvoicePayloadError(
                'Invalid LLM payload: each biznis_sk.items[] entry must be an object.',
                error_code='items_shape_invalid',
                details={'item_index': index},
                partial_payload=payload_snapshot,
            )
        candidate = {
            'polozka_povodna': raw_item.get('polozka_povodna'),
            'termin_sluzby_sk': raw_item.get('termin_sluzby_sk'),
            'mnozstvo': raw_item.get('mnozstvo'),
            'jednotka': raw_item.get('jednotka'),
            'cena_za_jednotku': raw_item.get('cena_za_jednotku'),
            'suma': raw_item.get('suma'),
            'item_description_raw': raw_item.get('item_description_raw'),
        }
        _resolve_service_candidate_or_raise(
            item_payload=candidate,
            payload_snapshot=payload_snapshot,
            item_index=index,
        )
        normalized_items.append(candidate)

    biznis_sk['items'] = normalized_items


def validate_invoice_phase2_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = _require_dict(payload, 'root')

    missing_sections = _REQUIRED_TOP_LEVEL_SECTIONS - set(data.keys())
    if missing_sections:
        missing = ', '.join(sorted(missing_sections))
        raise LlmInvoicePayloadError(f'Invalid LLM payload: missing top-level section(s): {missing}.')

    vstup = _require_dict(data['vstup'], 'vstup')
    zamer = _require_dict(data['zamer'], 'zamer')
    biznis_sk = _require_dict(data['biznis_sk'], 'biznis_sk')
    stopa = _require_dict(data['stopa'], 'stopa')

    if 'povodny_text' not in vstup or 'zisteny_jazyk' not in vstup:
        raise LlmInvoicePayloadError('Invalid LLM payload: vstup must include povodny_text and zisteny_jazyk.')
    if 'nazov' not in zamer or 'istota' not in zamer:
        raise LlmInvoicePayloadError('Invalid LLM payload: zamer must include nazov and istota.')

    missing_biznis = _REQUIRED_BIZNIS_FIELDS - set(biznis_sk.keys())
    if missing_biznis:
        missing = ', '.join(sorted(missing_biznis))
        raise LlmInvoicePayloadError(f'Invalid LLM payload: missing biznis_sk field(s): {missing}.')

    for trace_field in ('chyba_udaje', 'nejasnosti', 'poznamky_normalizacie'):
        if trace_field not in stopa or not isinstance(stopa[trace_field], list):
            raise LlmInvoicePayloadError(
                f'Invalid LLM payload: stopa.{trace_field} must be present and must be an array.'
            )

    payload_snapshot = {
        'vstup': dict(vstup),
        'zamer': dict(zamer),
        'biznis_sk': dict(biznis_sk),
        'stopa': dict(stopa),
    }
    biznis_sk['odberatel_kandidat'] = _validate_lookup_ready_customer_candidate(
        biznis_sk['odberatel_kandidat'],
        payload_snapshot=payload_snapshot,
    )
    _resolve_service_slots_or_raise(biznis_sk=biznis_sk, payload_snapshot=payload_snapshot)
    _validate_optional_items_or_raise(biznis_sk=biznis_sk, payload_snapshot=payload_snapshot)

    for key in tuple(biznis_sk.keys()):
        if key not in _REQUIRED_BIZNIS_FIELDS and key not in _OPTIONAL_BIZNIS_FIELDS and key != 'items':
            del biznis_sk[key]

    return data


async def parse_invoice_phase2_payload(text: str, api_key: str, model: str) -> dict[str, Any]:
    system_prompt = _PROMPT_PATH.read_text(encoding='utf-8')
    client = AsyncOpenAI(api_key=api_key)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text},
        ],
        response_format={'type': 'json_object'},
        temperature=0,
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)
    return validate_invoice_phase2_payload(parsed)
