from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from urllib.parse import urljoin

import aiohttp


RPO_BASE_URL = 'https://api.statistics.sk/rpo/v1/'
_MAX_RESPONSE_BYTES = 1_500_000


class RegistryLookupError(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryCompanyCandidate:
    subject_id: str
    name: str
    ico: str
    city: str | None
    short_address: str | None
    is_active: bool | None
    provider: str


@dataclass(frozen=True)
class RegistryCompanyDetails:
    subject_id: str
    name: str
    ico: str
    dic: str | None
    ic_dph: str | None
    address: str | None
    city: str | None
    is_active: bool | None
    provider_sources: tuple[str, ...]


class SlovakCompanyRegistry:
    def __init__(
        self,
        *,
        timeout_seconds: int = 5,
        max_results: int = 5,
        base_url: str = RPO_BASE_URL,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError('registry_timeout_out_of_range')
        if max_results < 1 or max_results > 10:
            raise ValueError('registry_max_results_out_of_range')
        self._timeout_seconds = timeout_seconds
        self._max_results = max_results
        self._base_url = base_url.rstrip('/') + '/'

    async def search(self, query: str) -> list[RegistryCompanyCandidate]:
        raw_query = query.strip()
        if not raw_query:
            return []
        ico_query = re.sub(r'\s+', '', raw_query)
        if re.fullmatch(r'\d{8}', ico_query):
            params = {'identifier': ico_query, 'onlyActive': 'true'}
        else:
            normalized_query = normalize_company_search_name(raw_query)
            if len(normalized_query) < 3:
                return []
            params = {'fullName': normalized_query, 'onlyActive': 'true'}

        payload = await self._request_json('search', params=params)
        rows = payload.get('results') if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RegistryLookupError('registry_search_shape_invalid')

        candidates = [candidate for row in rows if (candidate := _map_candidate(row)) is not None]
        candidates.sort(key=lambda item: _candidate_rank(item, raw_query))
        return candidates[: self._max_results]

    async def get_details(self, subject_id: str) -> RegistryCompanyDetails:
        if not re.fullmatch(r'\d+', subject_id.strip()):
            raise RegistryLookupError('registry_subject_id_invalid')
        payload = await self._request_json(f'entity/{subject_id.strip()}')
        details = _map_details(payload)
        if details is None:
            raise RegistryLookupError('registry_detail_shape_invalid')
        return details

    async def _request_json(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
    ) -> dict[str, object]:
        timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
        headers = {'Accept': 'application/json', 'User-Agent': 'OfficeFlow-FakturaBot/1.0'}
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(urljoin(self._base_url, path), params=params) as response:
                    if response.status != 200:
                        raise RegistryLookupError(f'registry_http_status_{response.status}')
                    if response.content_length is not None and response.content_length > _MAX_RESPONSE_BYTES:
                        raise RegistryLookupError('registry_response_too_large')
                    chunks: list[bytes] = []
                    received = 0
                    async for chunk in response.content.iter_chunked(65536):
                        received += len(chunk)
                        if received > _MAX_RESPONSE_BYTES:
                            raise RegistryLookupError('registry_response_too_large')
                        chunks.append(chunk)
        except RegistryLookupError:
            raise
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise RegistryLookupError('registry_unavailable') from exc

        try:
            decoded = b''.join(chunks).decode('utf-8')
            parsed = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryLookupError('registry_json_invalid') from exc
        if not isinstance(parsed, dict):
            raise RegistryLookupError('registry_json_shape_invalid')
        return parsed


def normalize_company_search_name(value: str) -> str:
    folded = unicodedata.normalize('NFKD', value.casefold())
    without_marks = ''.join(char for char in folded if not unicodedata.combining(char))
    tokens = re.findall(r'[0-9a-z]+', without_marks)
    suffixes = (
        ('spol', 's', 'r', 'o'),
        ('spol', 'sro'),
        ('s', 'r', 'o'),
        ('a', 's'),
        ('sro',),
        ('as',),
    )
    while tokens:
        matched = False
        for suffix in suffixes:
            if tuple(tokens[-len(suffix):]) == suffix:
                tokens = tokens[:-len(suffix)]
                matched = True
                break
        if not matched:
            break
    return ' '.join(tokens)


def _candidate_rank(candidate: RegistryCompanyCandidate, query: str) -> tuple[object, ...]:
    compact_query = re.sub(r'\s+', '', query)
    if re.fullmatch(r'\d{8}', compact_query):
        exact_ico = candidate.ico == compact_query
        return (0 if exact_ico else 1, candidate.name.casefold(), candidate.ico)
    normalized_query = normalize_company_search_name(query)
    normalized_name = normalize_company_search_name(candidate.name)
    query_tokens = normalized_query.split()
    name_tokens = normalized_name.split()
    exact = normalized_name == normalized_query
    starts = bool(query_tokens) and name_tokens[: len(query_tokens)] == query_tokens
    contains_all = bool(query_tokens) and all(token in name_tokens for token in query_tokens)
    return (
        0 if exact else 1,
        0 if starts else 1,
        0 if contains_all else 1,
        0 if candidate.is_active is not False else 1,
        candidate.name.casefold(),
        candidate.ico,
    )


def _map_candidate(value: object) -> RegistryCompanyCandidate | None:
    if not isinstance(value, dict):
        return None
    subject_id = str(value.get('id') or '').strip()
    name = _current_value(value.get('fullNames'))
    ico = _current_value(value.get('identifiers'))
    address_obj = _current_object(value.get('addresses'))
    if not subject_id.isdigit() or not name or not re.fullmatch(r'\d{8}', ico or ''):
        return None
    city = _nested_value(address_obj, 'municipality')
    return RegistryCompanyCandidate(
        subject_id=subject_id,
        name=name,
        ico=ico,
        city=city,
        short_address=_format_address(address_obj),
        is_active=not bool(value.get('termination')),
        provider='slovak_rpo',
    )


def _map_details(value: object) -> RegistryCompanyDetails | None:
    if not isinstance(value, dict):
        return None
    subject_id = str(value.get('id') or '').strip()
    name = _current_value(value.get('fullNames'))
    ico = _current_value(value.get('identifiers'))
    address_obj = _current_object(value.get('addresses'))
    address = _format_address(address_obj)
    if not subject_id.isdigit() or not name or not re.fullmatch(r'\d{8}', ico or ''):
        return None
    return RegistryCompanyDetails(
        subject_id=subject_id,
        name=name,
        ico=ico,
        dic=None,
        ic_dph=None,
        address=address,
        city=_nested_value(address_obj, 'municipality'),
        is_active=not bool(value.get('termination')),
        provider_sources=('slovak_rpo',),
    )


def _current_value(value: object) -> str | None:
    current = _current_object(value)
    if current is None:
        return None
    text = current.get('value')
    return str(text).strip() if text is not None and str(text).strip() else None


def _current_object(value: object) -> dict[str, object] | None:
    if not isinstance(value, list):
        return None
    rows = [row for row in value if isinstance(row, dict)]
    if not rows:
        return None
    active = [row for row in rows if not row.get('validTo')]
    selected = max(active or rows, key=lambda row: str(row.get('validFrom') or ''))
    return selected


def _nested_value(value: dict[str, object] | None, key: str) -> str | None:
    if not value:
        return None
    nested = value.get(key)
    if not isinstance(nested, dict):
        return None
    text = nested.get('value')
    return str(text).strip() if text is not None and str(text).strip() else None


def _format_address(value: dict[str, object] | None) -> str | None:
    if not value:
        return None
    street = str(value.get('street') or '').strip()
    reg_number = str(value.get('regNumber') or '').strip()
    building_number = str(value.get('buildingNumber') or '').strip()
    if reg_number == '0':
        reg_number = ''
    if building_number == '0':
        building_number = ''
    if reg_number and building_number:
        number = f'{reg_number}/{building_number}'
    else:
        number = building_number or reg_number
    street_line = ' '.join(part for part in (street, number) if part)
    postal_codes = value.get('postalCodes')
    postal = ''
    if isinstance(postal_codes, list) and postal_codes:
        postal = str(postal_codes[0] or '').strip()
    city = _nested_value(value, 'municipality') or ''
    locality = ' '.join(part for part in (postal, city) if part)
    address = ', '.join(part for part in (street_line, locality) if part)
    return address or None