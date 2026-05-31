from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import base64
import inspect
import json
from pathlib import Path

import pytest

from bot import google_drive_oauth_callback_app
from bot.config import Config
from bot.services import google_oauth_token_exchanger
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_ERROR_AUTH_REVOKED,
    GOOGLE_DRIVE_ERROR_CONNECTION,
    GOOGLE_DRIVE_ERROR_NEEDS_REAUTH,
    GOOGLE_DRIVE_ERROR_SCOPE_MISSING,
    GOOGLE_DRIVE_ERROR_UNKNOWN,
)
from bot.services.google_drive_oauth_callback_service import (
    GoogleOAuthInvalidGrantError,
    GoogleOAuthTokenExchangeError,
)
from bot.services.google_drive_oauth_state_service import DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES
from bot.services.google_oauth_token_exchanger import (
    GOOGLE_DRIVE_FILE_SCOPE,
    GOOGLE_OAUTH_TOKEN_ENDPOINT,
    GoogleOAuthTokenExchanger,
)


AUTH_CODE = '4/0AfJohXn-raw-auth-code-secret'
CLIENT_ID = 'client-id.apps.googleusercontent.com'
CLIENT_SECRET = 'client-secret-value'
REDIRECT_URI = 'https://officeflow.example.test/oauth/google/callback'
ACCESS_TOKEN = 'ya29.access-token-secret'
REFRESH_TOKEN = '1//refresh-token-secret'
ID_TOKEN = 'header.payload.signature'
NOW = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)


@dataclass
class FakeHTTPClient:
    status: int = 200
    payload: dict[str, object] | None = None
    body: bytes | None = None
    exception: Exception | None = None
    calls: int = 0
    seen_url: str | None = None
    seen_data: dict[str, str] | None = None
    seen_timeout: float | None = None

    def post_form(
        self,
        *,
        url: str,
        data: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        self.calls += 1
        self.seen_url = url
        self.seen_data = dict(data)
        self.seen_timeout = timeout_seconds
        if self.exception is not None:
            raise self.exception
        if self.body is not None:
            return self.status, self.body
        assert self.payload is not None
        return self.status, json.dumps(self.payload).encode('utf-8')


def _id_token_payload(*, subject: str = 'google-subject-1', email: str = 'USER@Example.COM') -> str:
    payload = json.dumps({'sub': subject, 'email': email}, separators=(',', ':')).encode('utf-8')
    encoded = base64.urlsafe_b64encode(payload).decode('ascii').rstrip('=')
    return f'header.{encoded}.signature'


def _success_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        'access_token': ACCESS_TOKEN,
        'refresh_token': REFRESH_TOKEN,
        'expires_in': 3600,
        'scope': 'openid email profile https://www.googleapis.com/auth/drive.file',
        'token_type': 'Bearer',
        'id_token': _id_token_payload(),
    }
    payload.update(overrides)
    return payload


def _exchanger(
    http_client: FakeHTTPClient,
    *,
    client_secret: str = CLIENT_SECRET,
) -> GoogleOAuthTokenExchanger:
    return GoogleOAuthTokenExchanger(
        client_id=CLIENT_ID,
        client_secret=client_secret,
        http_client=http_client,
        now=NOW,
    )


def _exchange(http_client: FakeHTTPClient):
    return _exchanger(http_client).exchange_code(
        code=AUTH_CODE,
        redirect_uri=REDIRECT_URI,
        scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
    )


def _assert_safe_exception(exc: Exception) -> None:
    text = f'{exc!s}\n{exc!r}'
    forbidden = (
        AUTH_CODE,
        CLIENT_SECRET,
        ACCESS_TOKEN,
        REFRESH_TOKEN,
        ID_TOKEN,
        'raw_google_response',
    )
    assert not any(value in text for value in forbidden)


def test_success_exchange_returns_normalized_token_bundle() -> None:
    http_client = FakeHTTPClient(payload=_success_payload())

    bundle = _exchange(http_client)

    assert http_client.calls == 1
    assert http_client.seen_url == GOOGLE_OAUTH_TOKEN_ENDPOINT
    assert http_client.seen_timeout == 10.0
    assert http_client.seen_data == {
        'code': AUTH_CODE,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code',
    }
    assert bundle.access_token == ACCESS_TOKEN
    assert bundle.refresh_token == REFRESH_TOKEN
    assert bundle.expires_at == '2026-05-31T13:00:00+00:00'
    assert bundle.scope == (
        'openid',
        'email',
        'profile',
        GOOGLE_DRIVE_FILE_SCOPE,
    )
    assert bundle.token_type == 'Bearer'
    assert bundle.google_subject == 'google-subject-1'
    assert bundle.google_email == 'user@example.com'


def test_success_requires_refresh_token() -> None:
    http_client = FakeHTTPClient(payload=_success_payload(refresh_token=''))

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_NEEDS_REAUTH
    _assert_safe_exception(excinfo.value)


def test_success_validates_drive_file_scope() -> None:
    http_client = FakeHTTPClient(payload=_success_payload(scope='openid email profile'))

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_SCOPE_MISSING
    _assert_safe_exception(excinfo.value)


def test_scope_defaults_to_requested_scopes_when_response_omits_scope() -> None:
    payload = _success_payload()
    payload.pop('scope')
    http_client = FakeHTTPClient(payload=payload)

    bundle = _exchange(http_client)

    assert GOOGLE_DRIVE_FILE_SCOPE in bundle.scope


def test_invalid_grant_maps_to_auth_revoked() -> None:
    http_client = FakeHTTPClient(status=400, payload={'error': 'invalid_grant', 'error_description': 'raw_google_response'})

    with pytest.raises(GoogleOAuthInvalidGrantError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_AUTH_REVOKED
    _assert_safe_exception(excinfo.value)


def test_invalid_client_maps_to_bounded_connection_error() -> None:
    http_client = FakeHTTPClient(
        status=401,
        payload={'error': 'invalid_client', 'error_description': f'secret={CLIENT_SECRET}'},
    )

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_CONNECTION
    _assert_safe_exception(excinfo.value)


@pytest.mark.parametrize('provider_error', ['invalid_scope', 'insufficient_scope'])
def test_scope_provider_errors_map_to_scope_missing(provider_error: str) -> None:
    http_client = FakeHTTPClient(status=400, payload={'error': provider_error})

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_SCOPE_MISSING


def test_malformed_json_maps_to_bounded_connection_error() -> None:
    http_client = FakeHTTPClient(status=200, body=b'not-json raw_google_response')

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_CONNECTION
    _assert_safe_exception(excinfo.value)


def test_http_5xx_maps_to_bounded_connection_error() -> None:
    http_client = FakeHTTPClient(status=503, payload={'error': 'server_error', 'error_description': 'raw_google_response'})

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_CONNECTION
    _assert_safe_exception(excinfo.value)


def test_network_timeout_maps_to_bounded_connection_error() -> None:
    http_client = FakeHTTPClient(exception=TimeoutError(f'timeout code={AUTH_CODE} secret={CLIENT_SECRET}'))

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_CONNECTION
    _assert_safe_exception(excinfo.value)


def test_unexpected_http_client_exception_maps_to_unknown_without_raw_message() -> None:
    http_client = FakeHTTPClient(exception=RuntimeError(f'raw_google_response token={ACCESS_TOKEN}'))

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_UNKNOWN
    _assert_safe_exception(excinfo.value)


def test_missing_access_token_maps_to_connection_error() -> None:
    payload = _success_payload()
    payload.pop('access_token')
    http_client = FakeHTTPClient(payload=payload)

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    assert excinfo.value.error_code == GOOGLE_DRIVE_ERROR_CONNECTION


def test_exception_and_repr_do_not_include_code_secret_tokens_or_raw_response() -> None:
    http_client = FakeHTTPClient(
        status=400,
        payload={
            'error': 'invalid_client',
            'error_description': (
                f'raw_google_response code={AUTH_CODE} client_secret={CLIENT_SECRET} '
                f'access={ACCESS_TOKEN} refresh={REFRESH_TOKEN} id={ID_TOKEN}'
            ),
        },
    )

    with pytest.raises(GoogleOAuthTokenExchangeError) as excinfo:
        _exchange(http_client)

    _assert_safe_exception(excinfo.value)


def test_no_real_network_in_tests_uses_injected_http_client() -> None:
    http_client = FakeHTTPClient(payload=_success_payload())

    _exchange(http_client)

    assert http_client.calls == 1
    assert isinstance(http_client, FakeHTTPClient)


def test_callback_app_remains_fail_closed_and_exchanger_not_wired(tmp_path: Path) -> None:
    config = Config(
        bot_token='123:ABC',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'db.sqlite',
        storage_dir=tmp_path,
        google_oauth_client_id=CLIENT_ID,
        google_oauth_client_secret=CLIENT_SECRET,
        google_oauth_redirect_uri=REDIRECT_URI,
        google_token_crypto_secret='placeholder-secret',
    )

    with pytest.raises(RuntimeError, match='callback runtime is disabled'):
        google_drive_oauth_callback_app.create_callback_app_from_config(config)

    source = inspect.getsource(google_drive_oauth_callback_app)
    assert 'google_oauth_token_exchanger' not in source
    assert 'bot.services.google_oauth_token_exchanger' not in source


def test_product_truth_and_infohelp_are_not_changed() -> None:
    from bot.services.info_help import build_product_truth_guidance
    from bot.services.product_truth import ProductTruthStatus, get_capability

    result = get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Can bot save invoices to Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.UNSUPPORTED
    assert result.capability.runtime_owner is None
    assert answer is not None


def test_env_examples_contain_oauth_client_secret_placeholder_only() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for relative_path in ('.env.example', '.env.server.example'):
        content = (repo_root / relative_path).read_text(encoding='utf-8')

        assert 'GOOGLE_OAUTH_CLIENT_SECRET=' in content
        assert CLIENT_SECRET not in content
        assert ACCESS_TOKEN not in content
        assert REFRESH_TOKEN not in content


def test_token_exchanger_module_has_no_google_client_or_drive_upload_imports() -> None:
    source = inspect.getsource(google_oauth_token_exchanger)

    forbidden = (
        'googleapiclient',
        'google.auth',
        'archive_worker',
        'drive_adapter',
        'upload_file',
    )

    assert not any(name in source for name in forbidden)
