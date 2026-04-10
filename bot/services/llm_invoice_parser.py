import json
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


class LlmInvoicePayloadError(ValueError):
    pass


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LlmInvoicePayloadError(f'Invalid LLM payload: {path} must be an object.')
    return value


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
