from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI


_FIELDS = ['company_name', 'ico', 'dic', 'ic_dph', 'address', 'email', 'contact_person']


def _regex_extract(source: str, pattern: str, *, group_index: int = 1) -> str | None:
    match = re.search(pattern, source, flags=re.IGNORECASE)
    if not match:
        return None
    value = match.group(group_index).strip()
    return value or None


def _deterministic_contact_parse(source_text: str, company_hint: str | None) -> dict[str, str | None]:
    email = _regex_extract(source_text, r'([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})')
    ico = _regex_extract(source_text, r'\bI[ČC]O[:\s]*([0-9]{8})\b')
    dic = _regex_extract(source_text, r'\bDI[ČC][:\s]*([0-9]{10})\b')
    ic_dph = _regex_extract(
        source_text,
        r'\b(?:I[ČC]\s*DPH|IČDPH|VAT)[:\s]*([A-Z]{2}\s*[0-9]{8,12})\b',
    )
    if ic_dph:
        ic_dph = re.sub(r'\s+', '', ic_dph).upper()
    address = _regex_extract(source_text, r'(?:adresa|sídlo)[:\s]*([^\n]{8,120})')
    contact_person = _regex_extract(source_text, r'(?:kontakt|kontaktná osoba|zastúpen[ýa])[:\s]*([^\n]{4,80})')
    company = company_hint or _regex_extract(source_text, r'(?:objednávateľ|odberateľ|firma|spoločnosť)[:\s]*([^\n]{2,120})')
    if company:
        company = company.strip(' ,.;:')
    return {
        'company_name': company,
        'ico': ico,
        'dic': dic,
        'ic_dph': ic_dph,
        'address': address,
        'email': email,
        'contact_person': contact_person,
    }


async def extract_contact_draft(
    *,
    source_text: str,
    api_key: str | None,
    model: str,
    company_hint: str | None = None,
) -> dict[str, str | None]:
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
                            'Extract contact fields from supplied text. '
                            'Return strict JSON with keys: '
                            'company_name, ico, dic, ic_dph, address, email, contact_person, role_ambiguity. '
                            'Use null for unknown. role_ambiguity must be true/false.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'company_hint': company_hint,
                                'expected_fields': _FIELDS,
                                'source_text': source_text,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            parsed = json.loads(response.choices[0].message.content or '{}')
            result = {field: _sanitize_value(parsed.get(field)) for field in _FIELDS}
            role_ambiguity = bool(parsed.get('role_ambiguity', False))
            result['role_ambiguity'] = '1' if role_ambiguity else '0'
            if any(result.get(field) for field in _FIELDS):
                return result
        except Exception:
            pass

    result = _deterministic_contact_parse(source_text, company_hint=company_hint)
    lowered = source_text.lower()
    role_ambiguity = 'objednávateľ' in lowered and 'zhotoviteľ' in lowered and not company_hint
    result['role_ambiguity'] = '1' if role_ambiguity else '0'
    return result


def _sanitize_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    cleaned = value.strip()
    return cleaned or None
