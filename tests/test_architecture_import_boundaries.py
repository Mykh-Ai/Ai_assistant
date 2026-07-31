from __future__ import annotations

import importlib
import inspect

import pytest


NO_GOOGLE_OR_NETWORK_IMPORTS = (
    'googleapiclient',
    'google.auth',
    'requests',
    'httpx',
    'aiohttp',
    'socket',
)
NO_GOOGLE_OR_HTTP_IMPORTS = NO_GOOGLE_OR_NETWORK_IMPORTS[:-1]


@pytest.mark.contract
@pytest.mark.parametrize(
    ('module_path', 'forbidden_imports', 'required_source_tokens'),
    [
        pytest.param(
            'bot.services.accounting_document_archive_service',
            NO_GOOGLE_OR_HTTP_IMPORTS,
            (),
            id='accounting-archive-service',
        ),
        pytest.param(
            'bot.services.accounting_original_cleanup_service',
            NO_GOOGLE_OR_NETWORK_IMPORTS,
            (),
            id='accounting-original-cleanup-service',
        ),
        pytest.param(
            'bot.services.archive_job_service',
            NO_GOOGLE_OR_HTTP_IMPORTS,
            (),
            id='archive-job-service',
        ),
        pytest.param(
            'bot.services.archive_worker',
            NO_GOOGLE_OR_NETWORK_IMPORTS,
            ('claim_next_runnable_job',),
            id='archive-worker',
        ),
        pytest.param(
            'bot.services.google_drive_connection_service',
            NO_GOOGLE_OR_NETWORK_IMPORTS,
            (),
            id='google-drive-connection-service',
        ),
        pytest.param(
            'bot.services.google_drive_oauth_state_service',
            NO_GOOGLE_OR_NETWORK_IMPORTS,
            (),
            id='google-drive-oauth-state-service',
        ),
        pytest.param(
            'bot.services.google_drive_oauth_callback_service',
            NO_GOOGLE_OR_NETWORK_IMPORTS,
            (),
            id='google-drive-oauth-callback-service',
        ),
        pytest.param(
            'bot.handlers.settings',
            NO_GOOGLE_OR_NETWORK_IMPORTS,
            (),
            id='google-drive-setup-commands',
        ),
        pytest.param(
            'bot.services.google_oauth_token_exchanger',
            (
                'googleapiclient',
                'google.auth',
                'archive_worker',
                'drive_adapter',
                'upload_file',
            ),
            (),
            id='google-oauth-token-exchanger',
        ),
        pytest.param(
            'bot.services.token_crypto',
            NO_GOOGLE_OR_NETWORK_IMPORTS,
            (),
            id='token-crypto',
        ),
    ],
)
def test_module_import_boundary(
    module_path: str,
    forbidden_imports: tuple[str, ...],
    required_source_tokens: tuple[str, ...],
) -> None:
    module = importlib.import_module(module_path)
    source = inspect.getsource(module)
    violations = tuple(token for token in forbidden_imports if token in source)

    assert not violations, f'{module_path} contains forbidden import-boundary tokens: {violations}'
    for token in required_source_tokens:
        assert token in source, f'{module_path} is missing required architecture token: {token}'
