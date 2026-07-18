from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
from typing import Protocol
from urllib.parse import quote, urljoin

import aiohttp

from bot.services.slovak_company_registry import RegistryCompanyDetails
from bot.services.validation import validate_dic, validate_ic_dph, validate_ico


FINANCNA_SPRAVA_BASE_URL = 'https://iz.opendata.financnasprava.sk/api/'
_MAX_TAX_RESPONSE_BYTES = 512_000


class TaxRegistryLookupError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class TaxRegistryDetails:
    ico: str
    dic: str | None
    ic_dph: str | None
    is_vat_registered: bool | None
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class TaxListSpec:
    slug: str
    ico_field: str
    value_field: str
    source_id: str


@dataclass(frozen=True)
class TaxRegistrySchema:
    income_tax: TaxListSpec
    vat: TaxListSpec


class CompanyRegistryDetailsProvider(Protocol):
    async def get_details(self, subject_id: str) -> RegistryCompanyDetails:
        ...


class TaxDetailsProvider(Protocol):
    async def lookup_by_ico(self, ico: str) -> TaxRegistryDetails | None:
        ...


@dataclass(frozen=True)
class AggregatedRegistryDetails:
    details: RegistryCompanyDetails
    tax_error_code: str | None = None


def verified_financna_sprava_schema() -> TaxRegistrySchema:
    """Return mappings verified against the official API on 2026-07-18."""

    return TaxRegistrySchema(
        income_tax=TaxListSpec(
            slug='ds_dsrdp',
            ico_field='ico',
            value_field='dic',
            source_id='financna_sprava_income_tax',
        ),
        vat=TaxListSpec(
            slug='ds_dphs',
            ico_field='ico',
            value_field='ic_dph',
            source_id='financna_sprava_vat',
        ),
    )


class SlovakTaxRegistry:
    def __init__(
        self,
        *,
        enabled: bool,
        api_key: str | None,
        schema: TaxRegistrySchema | None,
        timeout_seconds: int = 5,
        base_url: str = FINANCNA_SPRAVA_BASE_URL,
    ) -> None:
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError('tax_registry_timeout_out_of_range')
        self._enabled = enabled
        self._api_key = (api_key or '').strip() or None
        self._schema = schema
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url.rstrip('/') + '/'

    async def lookup_by_ico(self, ico: str) -> TaxRegistryDetails | None:
        normalized_ico = _normalize_ico(ico)
        if normalized_ico is None:
            raise TaxRegistryLookupError('tax_registry_malformed')
        if not self._enabled:
            raise TaxRegistryLookupError('tax_registry_disabled')
        if self._api_key is None or self._schema is None:
            raise TaxRegistryLookupError('tax_registry_not_configured')

        income_rows = await self._search(self._schema.income_tax, normalized_ico)
        vat_rows = await self._search(self._schema.vat, normalized_ico)
        dic = _resolve_exact_value(
            income_rows,
            ico=normalized_ico,
            spec=self._schema.income_tax,
            validator=validate_dic,
            normalizer=lambda value: value.strip(),
        )
        ic_dph = _resolve_exact_value(
            vat_rows,
            ico=normalized_ico,
            spec=self._schema.vat,
            validator=validate_ic_dph,
            normalizer=lambda value: re.sub(r'\s+', '', value).upper(),
        )
        if dic is None and ic_dph is None:
            return None
        source_ids = tuple(
            source_id
            for source_id, value in (
                (self._schema.income_tax.source_id, dic),
                (self._schema.vat.source_id, ic_dph),
            )
            if value is not None
        )
        return TaxRegistryDetails(
            ico=normalized_ico,
            dic=dic,
            ic_dph=ic_dph,
            is_vat_registered=True if ic_dph is not None else None,
            source_ids=source_ids,
        )

    async def _search(self, spec: TaxListSpec, ico: str) -> list[dict[str, object]]:
        payload = await self._request_json(
            f'data/{quote(spec.slug, safe="")}/search',
            params={'page': '1', 'column': spec.ico_field, 'search': ico},
        )
        if payload is None:
            return []
        required = {'page', 'pages', 'itemsCount', 'itemsPerPage', 'data'}
        if not isinstance(payload, dict) or not required.issubset(payload):
            raise TaxRegistryLookupError('tax_registry_malformed')
        if (
            not isinstance(payload['page'], int)
            or not isinstance(payload['pages'], int)
            or not isinstance(payload['itemsCount'], int)
            or not isinstance(payload['itemsPerPage'], int)
            or not isinstance(payload['data'], list)
            or payload['page'] != 1
            or payload['pages'] < 0
            or payload['itemsCount'] < 0
            or payload['itemsPerPage'] < 0
        ):
            raise TaxRegistryLookupError('tax_registry_malformed')
        if payload['pages'] > 1 or payload['itemsCount'] > payload['itemsPerPage']:
            raise TaxRegistryLookupError('tax_registry_conflict')
        rows = payload['data']
        if any(not isinstance(row, dict) for row in rows):
            raise TaxRegistryLookupError('tax_registry_malformed')
        return rows

    async def _request_json(
        self,
        path: str,
        *,
        params: dict[str, str],
    ) -> dict[str, object] | None:
        if self._api_key is None:
            raise TaxRegistryLookupError('tax_registry_not_configured')
        timeout = aiohttp.ClientTimeout(
            total=self._timeout_seconds,
            connect=min(self._timeout_seconds, 5),
            sock_read=self._timeout_seconds,
        )
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'OfficeFlow-FakturaBot/1.0',
            'key': self._api_key,
        }
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(urljoin(self._base_url, path), params=params) as response:
                    if response.status == 404:
                        return None
                    if response.status in {401, 403}:
                        raise TaxRegistryLookupError('tax_registry_unauthorized')
                    if response.status == 429:
                        raise TaxRegistryLookupError('tax_registry_rate_limited')
                    if response.status >= 500:
                        raise TaxRegistryLookupError('tax_registry_unavailable')
                    if response.status != 200:
                        raise TaxRegistryLookupError('tax_registry_malformed')
                    if response.content_length is not None and response.content_length > _MAX_TAX_RESPONSE_BYTES:
                        raise TaxRegistryLookupError('tax_registry_malformed')
                    chunks: list[bytes] = []
                    received = 0
                    async for chunk in response.content.iter_chunked(65536):
                        received += len(chunk)
                        if received > _MAX_TAX_RESPONSE_BYTES:
                            raise TaxRegistryLookupError('tax_registry_malformed')
                        chunks.append(chunk)
        except TaxRegistryLookupError:
            raise
        except (aiohttp.ClientError, TimeoutError):
            raise TaxRegistryLookupError('tax_registry_unavailable') from None

        try:
            parsed = json.loads(b''.join(chunks).decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TaxRegistryLookupError('tax_registry_malformed') from None
        if not isinstance(parsed, dict):
            raise TaxRegistryLookupError('tax_registry_malformed')
        return parsed


class SlovakCompanyDetailsAggregator:
    def __init__(
        self,
        registry: CompanyRegistryDetailsProvider,
        tax_registry: TaxDetailsProvider | None,
    ) -> None:
        self._registry = registry
        self._tax_registry = tax_registry

    async def get_details(self, subject_id: str) -> AggregatedRegistryDetails:
        details = await self._registry.get_details(subject_id)
        if self._tax_registry is None:
            return AggregatedRegistryDetails(details=details)
        try:
            tax = await self._tax_registry.lookup_by_ico(details.ico)
        except TaxRegistryLookupError as exc:
            return AggregatedRegistryDetails(details=details, tax_error_code=exc.code)
        if tax is None:
            return AggregatedRegistryDetails(details=details)
        if tax.ico != details.ico:
            return AggregatedRegistryDetails(details=details, tax_error_code='tax_registry_conflict')
        enriched = replace(
            details,
            dic=tax.dic,
            ic_dph=tax.ic_dph,
            provider_sources=tuple(dict.fromkeys((*details.provider_sources, 'financna_sprava'))),
        )
        return AggregatedRegistryDetails(details=enriched)


def _normalize_ico(value: object) -> str | None:
    normalized = re.sub(r'\s+', '', str(value or ''))
    return normalized if validate_ico(normalized) else None


def _resolve_exact_value(
    rows: list[dict[str, object]],
    *,
    ico: str,
    spec: TaxListSpec,
    validator,
    normalizer,
) -> str | None:
    exact_rows = [row for row in rows if _normalize_ico(row.get(spec.ico_field)) == ico]
    if not exact_rows:
        return None
    values: set[str] = set()
    for row in exact_rows:
        raw_value = row.get(spec.value_field)
        if raw_value is None:
            raise TaxRegistryLookupError('tax_registry_malformed')
        value = normalizer(str(raw_value))
        if not validator(value):
            raise TaxRegistryLookupError('tax_registry_malformed')
        values.add(value)
    if len(values) != 1:
        raise TaxRegistryLookupError('tax_registry_conflict')
    return next(iter(values))
