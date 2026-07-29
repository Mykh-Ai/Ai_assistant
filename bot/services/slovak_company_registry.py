from __future__ import annotations

from dataclasses import dataclass, replace
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
    match_kind: str = 'exact_name'


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


@dataclass(frozen=True)
class CompanyNameForms:
    normalized_full: str
    normalized_core: str
    full_tokens: tuple[str, ...]
    core_tokens: tuple[str, ...]
    legal_suffix: str | None


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

    async def search(
        self, query: str, *, only_active: bool = True
    ) -> list[RegistryCompanyCandidate]:
        raw_query = query.strip()
        if not raw_query:
            return []
        ico_query = re.sub(r'\s+', '', raw_query)
        if re.fullmatch(r'\d{8}', ico_query):
            params = {
                'identifier': ico_query,
                'onlyActive': 'true' if only_active else 'false',
            }
        else:
            normalized_query = normalize_company_search_name(raw_query)
            if len(normalized_query) < 3:
                return []
            params = {
                'fullName': normalized_query,
                'onlyActive': 'true' if only_active else 'false',
            }

        payload = await self._request_json('search', params=params)
        rows = payload.get('results') if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise RegistryLookupError('registry_search_shape_invalid')

        candidates = [candidate for row in rows if (candidate := _map_candidate(row)) is not None]
        return _rank_and_filter_candidates(candidates, raw_query, max_results=self._max_results)

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
    return normalize_company_name_forms(value).normalized_core


def normalize_company_name_forms(value: str) -> CompanyNameForms:
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
    suffix_names = ('sro', 'sro', 'sro', 'as', 'sro', 'as')
    core_tokens = tuple(tokens)
    legal_suffix = None
    for suffix, canonical_suffix in zip(suffixes, suffix_names, strict=True):
        if tuple(tokens[-len(suffix):]) == suffix:
            core_tokens = tuple(tokens[:-len(suffix)])
            legal_suffix = canonical_suffix
            break
    full_tokens = core_tokens + ((legal_suffix,) if legal_suffix else ())
    return CompanyNameForms(
        normalized_full=' '.join(full_tokens),
        normalized_core=' '.join(core_tokens),
        full_tokens=full_tokens,
        core_tokens=core_tokens,
        legal_suffix=legal_suffix,
    )


def _rank_and_filter_candidates(
    candidates: list[RegistryCompanyCandidate], query: str, *, max_results: int,
) -> list[RegistryCompanyCandidate]:
    compact_query = re.sub(r'\s+', '', query)
    if re.fullmatch(r'\d{8}', compact_query):
        exact = [candidate for candidate in candidates if candidate.ico == compact_query]
        exact.sort(key=lambda item: (item.is_active is False, item.name.casefold(), item.ico))
        return [replace(candidate, match_kind='exact_ico') for candidate in exact[:max_results]]
    scored = []
    for candidate in candidates:
        match = _candidate_match(candidate, query)
        if match is not None:
            scored.append((match[0], match[1], candidate))
    exact = [item for item in scored if item[0] in {1, 2, 3}]
    if exact:
        exact.sort(key=lambda item: item[1])
        return [
            replace(item[2], match_kind='exact_name')
            for item in exact[:max_results]
        ]
    scored.sort(key=lambda item: item[1])
    return [replace(item[2], match_kind='suggested') for item in scored[:max_results]]


def _candidate_match(
    candidate: RegistryCompanyCandidate, query: str,
) -> tuple[int, tuple[object, ...]] | None:
    query_forms = normalize_company_name_forms(query)
    name_forms = normalize_company_name_forms(candidate.name)
    if not query_forms.core_tokens or not name_forms.core_tokens:
        return None
    if query_forms.normalized_full == name_forms.normalized_full:
        match_class = 1
    elif query_forms.normalized_core == name_forms.normalized_core:
        match_class = 2
    elif query_forms.core_tokens == name_forms.core_tokens:
        match_class = 3
    elif all(token in name_forms.core_tokens for token in query_forms.core_tokens):
        match_class = 4
    else:
        partial_score = _partial_name_score(query_forms, name_forms)
        if partial_score is None:
            return None
        match_class = 5
        return match_class, (
            match_class,
            0 if candidate.is_active is not False else 1,
            -partial_score,
            candidate.name.casefold(),
            candidate.ico,
        )
    return match_class, (
        match_class,
        0 if candidate.is_active is not False else 1,
        candidate.name.casefold(),
        candidate.ico,
    )


def _partial_name_score(query: CompanyNameForms, candidate: CompanyNameForms) -> float | None:
    query_compact = ''.join(query.core_tokens)
    candidate_compact = ''.join(candidate.core_tokens)
    if not query_compact or not candidate_compact:
        return None
    if query_compact == candidate_compact:
        return 0.98
    shortest = min(len(query_compact), len(candidate_compact))
    longest = max(len(query_compact), len(candidate_compact))
    if shortest >= 5 and _bounded_edit_distance(query_compact, candidate_compact, maximum=1) <= 1:
        return 0.9 + (shortest / longest) * 0.05
    token_scores: list[float] = []
    for query_token in query.core_tokens:
        best = 0.0
        for candidate_token in candidate.core_tokens:
            if query_token == candidate_token:
                best = 1.0
            elif min(len(query_token), len(candidate_token)) >= 3 and (
                candidate_token.startswith(query_token) or query_token.startswith(candidate_token)
            ):
                best = max(
                    best,
                    min(len(query_token), len(candidate_token))
                    / max(len(query_token), len(candidate_token)),
                )
            elif len(query_token) >= 3 and (
                candidate_token.startswith(query_token) or candidate_token.endswith(query_token)
            ):
                coverage = len(query_token) / len(candidate_token)
                if coverage >= 0.4:
                    best = max(best, coverage * 0.8)
        if best:
            token_scores.append(best)
    if len(token_scores) != len(query.core_tokens):
        return None
    score = sum(token_scores) / len(token_scores)
    return score if score >= 0.4 else None


def _bounded_edit_distance(left: str, right: str, *, maximum: int) -> int:
    if abs(len(left) - len(right)) > maximum:
        return maximum + 1
    previous = list(range(len(right) + 1))
    for row_index, left_char in enumerate(left, start=1):
        current = [row_index]
        row_minimum = row_index
        for column_index, right_char in enumerate(right, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column_index] + 1,
                previous[column_index - 1] + (left_char != right_char),
            ))
            row_minimum = min(row_minimum, current[-1])
        if row_minimum > maximum:
            return maximum + 1
        previous = current
    return previous[-1]


def _candidate_rank(candidate: RegistryCompanyCandidate, query: str) -> tuple[object, ...]:
    match = _candidate_match(candidate, query)
    return match[1] if match is not None else (99, candidate.name.casefold(), candidate.ico)


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