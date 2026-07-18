from __future__ import annotations

import asyncio
import json

import pytest

from bot.config import load_config
from bot.services.slovak_company_registry import RegistryCompanyDetails
from bot.services.slovak_tax_registry import (
    SlovakCompanyDetailsAggregator,
    SlovakTaxRegistry,
    TaxListSpec,
    TaxRegistryDetails,
    TaxRegistryLookupError,
    TaxRegistrySchema,
    verified_financna_sprava_schema,
)


SCHEMA = TaxRegistrySchema(
    income_tax=TaxListSpec(
        slug='verified-income-slug', ico_field='ICO', value_field='DIC',
        source_id='financna_sprava_income_tax',
    ),
    vat=TaxListSpec(
        slug='verified-vat-slug', ico_field='ICO', value_field='IC_DPH',
        source_id='financna_sprava_vat',
    ),
)


def test_production_schema_matches_key_backed_official_audit() -> None:
    assert verified_financna_sprava_schema() == TaxRegistrySchema(
        income_tax=TaxListSpec(
            slug='ds_dsrdp', ico_field='ico', value_field='dic',
            source_id='financna_sprava_income_tax',
        ),
        vat=TaxListSpec(
            slug='ds_dphs', ico_field='ico', value_field='ic_dph',
            source_id='financna_sprava_vat',
        ),
    )


def _payload(rows: list[object], **overrides) -> dict[str, object]:
    result = {
        'page': 1,
        'pages': 1 if rows else 0,
        'itemsCount': len(rows),
        'itemsPerPage': max(1, len(rows)),
        'data': rows,
    }
    result.update(overrides)
    return result


class _StubTaxRegistry(SlovakTaxRegistry):
    def __init__(self, responses, *, enabled=True, api_key='secret', schema=SCHEMA) -> None:
        super().__init__(enabled=enabled, api_key=api_key, schema=schema)
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def _request_json(self, path: str, *, params: dict[str, str]):
        self.calls.append((path, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_exact_ico_returns_valid_dic_and_official_ic_dph() -> None:
    registry = _StubTaxRegistry([
        _payload([{'ICO': '56055552', 'DIC': '2122222222', 'NAZOV_DS': 'Zevs'}]),
        _payload([{'ICO': '56055552', 'IC_DPH': 'SK2122222222'}]),
    ])

    result = asyncio.run(registry.lookup_by_ico('56055552'))

    assert result == TaxRegistryDetails(
        ico='56055552', dic='2122222222', ic_dph='SK2122222222',
        is_vat_registered=True,
        source_ids=('financna_sprava_income_tax', 'financna_sprava_vat'),
    )
    assert registry.calls == [
        ('data/verified-income-slug/search', {'page': '1', 'column': 'ICO', 'search': '56055552'}),
        ('data/verified-vat-slug/search', {'page': '1', 'column': 'ICO', 'search': '56055552'}),
    ]


def test_missing_vat_result_keeps_ic_dph_null_without_inference() -> None:
    registry = _StubTaxRegistry([
        _payload([{'ICO': '56055552', 'DIC': '2122222222'}]),
        _payload([]),
    ])

    result = asyncio.run(registry.lookup_by_ico('56055552'))

    assert result is not None
    assert result.dic == '2122222222'
    assert result.ic_dph is None
    assert result.is_vat_registered is None
    assert result.ic_dph != f'SK{result.dic}'


def test_name_only_and_wrong_ico_rows_are_rejected() -> None:
    registry = _StubTaxRegistry([
        _payload([
            {'NAZOV_DS': 'Zevs', 'DIC': '2122222222'},
            {'ICO': '11111111', 'DIC': '2122222222'},
        ]),
        _payload([{'ICO': '11111111', 'IC_DPH': 'SK2122222222'}]),
    ])

    assert asyncio.run(registry.lookup_by_ico('56055552')) is None


@pytest.mark.parametrize(
    ('income_rows', 'vat_rows', 'error_code'),
    [
        ([{'ICO': '56055552', 'DIC': '2122222222'}, {'ICO': '56055552', 'DIC': '2122222223'}], [], 'tax_registry_conflict'),
        ([{'ICO': '56055552', 'DIC': 'invalid'}], [], 'tax_registry_malformed'),
        ([], [{'ICO': '56055552', 'IC_DPH': 'invalid'}], 'tax_registry_malformed'),
        ([], [{'ICO': '56055552', 'IC_DPH': 'SK2122222222'}, {'ICO': '56055552', 'IC_DPH': 'SK2122222223'}], 'tax_registry_conflict'),
    ],
)
def test_invalid_or_conflicting_exact_rows_fail_closed(income_rows, vat_rows, error_code) -> None:
    registry = _StubTaxRegistry([_payload(income_rows), _payload(vat_rows)])

    with pytest.raises(TaxRegistryLookupError, match=error_code):
        asyncio.run(registry.lookup_by_ico('56055552'))


@pytest.mark.parametrize(
    ('enabled', 'api_key', 'schema', 'error_code'),
    [
        (False, 'secret', SCHEMA, 'tax_registry_disabled'),
        (True, None, SCHEMA, 'tax_registry_not_configured'),
        (True, 'secret', None, 'tax_registry_not_configured'),
    ],
)
def test_disabled_missing_key_or_unverified_schema_makes_no_call(enabled, api_key, schema, error_code) -> None:
    registry = _StubTaxRegistry([], enabled=enabled, api_key=api_key, schema=schema)

    with pytest.raises(TaxRegistryLookupError, match=error_code):
        asyncio.run(registry.lookup_by_ico('56055552'))
    assert registry.calls == []


@pytest.mark.parametrize('payload', [
    {'data': []},
    _payload([], page='1'),
    _payload([None]),
    _payload([], pages=2, itemsCount=2, itemsPerPage=1),
])
def test_unexpected_or_truncated_schema_fails_closed(payload) -> None:
    registry = _StubTaxRegistry([payload, _payload([])])

    with pytest.raises(TaxRegistryLookupError, match='tax_registry_(malformed|conflict)'):
        asyncio.run(registry.lookup_by_ico('56055552'))


class _FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_chunked(self, _size: int):
        for chunk in self._chunks:
            yield chunk


class _FakeResponse:
    def __init__(self, status: int, body: bytes, *, content_length=None, enter_error=None) -> None:
        self.status = status
        self.content_length = len(body) if content_length is None else content_length
        self.content = _FakeContent([body])
        self._enter_error = enter_error

    async def __aenter__(self):
        if self._enter_error:
            raise self._enter_error
        return self

    async def __aexit__(self, *_args):
        return False


class _FakeSession:
    def __init__(self, response: _FakeResponse, captured: dict, **kwargs) -> None:
        self._response = response
        captured['session_kwargs'] = kwargs
        self._captured = captured

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def get(self, url, *, params):
        self._captured['url'] = url
        self._captured['params'] = params
        return self._response


def _patch_session(monkeypatch, *, status=200, body=None, content_length=None, enter_error=None):
    from bot.services import slovak_tax_registry as module

    captured: dict = {}
    encoded = json.dumps(_payload([])).encode() if body is None else body
    response = _FakeResponse(
        status, encoded, content_length=content_length, enter_error=enter_error,
    )

    def factory(**kwargs):
        return _FakeSession(response, captured, **kwargs)

    monkeypatch.setattr(module.aiohttp, 'ClientSession', factory)
    return captured


@pytest.mark.parametrize(
    ('status', 'code'),
    [
        (401, 'tax_registry_unauthorized'),
        (403, 'tax_registry_unauthorized'),
        (429, 'tax_registry_rate_limited'),
        (500, 'tax_registry_unavailable'),
        (503, 'tax_registry_unavailable'),
    ],
)
def test_http_statuses_map_to_bounded_errors(monkeypatch, status, code) -> None:
    _patch_session(monkeypatch, status=status)
    registry = SlovakTaxRegistry(enabled=True, api_key='secret', schema=SCHEMA)

    with pytest.raises(TaxRegistryLookupError, match=code):
        asyncio.run(registry._request_json('path', params={'page': '1'}))


def test_timeout_malformed_json_and_oversized_response_fail_closed(monkeypatch) -> None:
    registry = SlovakTaxRegistry(enabled=True, api_key='secret', schema=SCHEMA)
    _patch_session(monkeypatch, enter_error=TimeoutError())
    with pytest.raises(TaxRegistryLookupError, match='tax_registry_unavailable'):
        asyncio.run(registry._request_json('path', params={'page': '1'}))

    _patch_session(monkeypatch, body=b'{bad json')
    with pytest.raises(TaxRegistryLookupError, match='tax_registry_malformed'):
        asyncio.run(registry._request_json('path', params={'page': '1'}))

    _patch_session(monkeypatch, content_length=512_001)
    with pytest.raises(TaxRegistryLookupError, match='tax_registry_malformed'):
        asyncio.run(registry._request_json('path', params={'page': '1'}))


def test_api_key_is_only_in_header_and_absent_from_errors_and_logs(monkeypatch, caplog) -> None:
    captured = _patch_session(monkeypatch, status=401)
    key = 'highly-secret-value'
    registry = SlovakTaxRegistry(enabled=True, api_key=key, schema=SCHEMA)

    with pytest.raises(TaxRegistryLookupError) as raised:
        asyncio.run(registry._request_json('path', params={'search': '56055552'}))

    assert captured['session_kwargs']['headers']['key'] == key
    assert key not in str(raised.value)
    assert key not in caplog.text
    assert key not in captured['url']


class _RegistryDetailsFake:
    async def get_details(self, _subject_id: str) -> RegistryCompanyDetails:
        return RegistryCompanyDetails(
            subject_id='1', name='Zevs s.r.o.', ico='56055552', dic=None,
            ic_dph=None, address='Hlavn? 1, Bratislava', city='Bratislava',
            is_active=True, provider_sources=('slovak_rpo',),
        )


class _TaxDetailsFake:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    async def lookup_by_ico(self, ico: str):
        self.calls.append(ico)
        if self.error:
            raise self.error
        return self.result


def test_aggregator_merges_validated_tax_fields_and_preserves_rpo_on_failure() -> None:
    tax = _TaxDetailsFake(TaxRegistryDetails(
        ico='56055552', dic='2122222222', ic_dph=None,
        is_vat_registered=None, source_ids=('financna_sprava_income_tax',),
    ))
    success = asyncio.run(SlovakCompanyDetailsAggregator(
        _RegistryDetailsFake(), tax,
    ).get_details('1'))
    assert success.details.dic == '2122222222'
    assert success.details.ic_dph is None
    assert success.details.provider_sources == ('slovak_rpo', 'financna_sprava')
    assert tax.calls == ['56055552']

    failure_tax = _TaxDetailsFake(error=TaxRegistryLookupError('tax_registry_unavailable'))
    failure = asyncio.run(SlovakCompanyDetailsAggregator(
        _RegistryDetailsFake(), failure_tax,
    ).get_details('1'))
    assert failure.details.dic is None
    assert failure.details.provider_sources == ('slovak_rpo',)
    assert failure.tax_error_code == 'tax_registry_unavailable'


def test_tax_configuration_is_disabled_by_default_and_secret_is_not_rendered(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv('BOT_TOKEN', 'token')
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'bot.db'))
    monkeypatch.setenv('STORAGE_DIR', str(tmp_path / 'storage'))
    monkeypatch.delenv('CONTACT_TAX_LOOKUP_ENABLED', raising=False)
    monkeypatch.delenv('FINANCNA_SPRAVA_API_KEY', raising=False)
    monkeypatch.delenv('FINANCNA_SPRAVA_TIMEOUT_SECONDS', raising=False)

    config = load_config()

    assert config.contact_tax_lookup_enabled is False
    assert config.financna_sprava_api_key is None
    assert config.financna_sprava_timeout_seconds == 5
    assert 'FINANCNA_SPRAVA_API_KEY' not in repr(config)


def test_tax_configuration_accepts_bounded_timeout_and_rejects_above_30(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv('BOT_TOKEN', 'token')
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'bot.db'))
    monkeypatch.setenv('STORAGE_DIR', str(tmp_path / 'storage'))
    monkeypatch.setenv('CONTACT_TAX_LOOKUP_ENABLED', '1')
    monkeypatch.setenv('FINANCNA_SPRAVA_API_KEY', 'secret')
    monkeypatch.setenv('FINANCNA_SPRAVA_TIMEOUT_SECONDS', '30')
    assert load_config().financna_sprava_timeout_seconds == 30

    monkeypatch.setenv('FINANCNA_SPRAVA_TIMEOUT_SECONDS', '31')
    with pytest.raises(RuntimeError, match='FINANCNA_SPRAVA_TIMEOUT_SECONDS must be at most 30'):
        load_config()
