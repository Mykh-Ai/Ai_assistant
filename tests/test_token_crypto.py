from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from bot.services import token_crypto
from bot.services.token_crypto import (
    DeterministicFakeTokenCryptoProvider,
    EncryptedToken,
    FernetTokenCryptoProvider,
    TokenCryptoError,
    UnconfiguredTokenCryptoProvider,
)


def test_deterministic_fake_crypto_round_trips_without_plaintext_ciphertext() -> None:
    crypto = DeterministicFakeTokenCryptoProvider(key_id='test-key')

    encrypted = crypto.encrypt_token('refresh-token-secret')
    decrypted = crypto.decrypt_token(encrypted)

    assert encrypted.key_id == 'test-key'
    assert encrypted.version == 1
    assert encrypted.ciphertext != b'refresh-token-secret'
    assert b'refresh-token-secret' not in encrypted.ciphertext
    assert decrypted == b'refresh-token-secret'


def test_deterministic_fake_crypto_rejects_wrong_key() -> None:
    encrypted = DeterministicFakeTokenCryptoProvider(key_id='key-a').encrypt_token('token')

    with pytest.raises(TokenCryptoError, match='token_key_mismatch'):
        DeterministicFakeTokenCryptoProvider(key_id='key-b').decrypt_token(encrypted)


def test_unconfigured_crypto_provider_requires_future_secret_wiring() -> None:
    crypto = UnconfiguredTokenCryptoProvider()

    with pytest.raises(TokenCryptoError, match='token_crypto_not_configured'):
        crypto.encrypt_token('token')
    with pytest.raises(TokenCryptoError, match='token_crypto_not_configured'):
        crypto.decrypt_token(EncryptedToken(ciphertext=b'ciphertext', key_id='key'))


def test_fernet_crypto_rejects_missing_secret() -> None:
    for secret in (None, '', b''):
        with pytest.raises(TokenCryptoError, match='token_crypto_secret_required'):
            FernetTokenCryptoProvider(secret=secret, key_id='prod-key')


def test_fernet_crypto_rejects_invalid_secret_without_echoing_value() -> None:
    raw_secret = 'not-a-valid-fernet-secret'

    with pytest.raises(TokenCryptoError) as excinfo:
        FernetTokenCryptoProvider(secret=raw_secret, key_id='prod-key')

    assert str(excinfo.value) == 'token_crypto_secret_invalid'
    assert raw_secret not in str(excinfo.value)
    assert raw_secret not in repr(excinfo.value)


def test_fernet_crypto_round_trips_with_authenticated_ciphertext() -> None:
    secret = Fernet.generate_key()
    crypto = FernetTokenCryptoProvider(secret=secret, key_id='google-token-key-v1')

    encrypted = crypto.encrypt_token('refresh-token-secret')
    decrypted = crypto.decrypt_token(encrypted)

    assert encrypted.key_id == 'google-token-key-v1'
    assert encrypted.version == 1
    assert encrypted.ciphertext != b'refresh-token-secret'
    assert b'refresh-token-secret' not in encrypted.ciphertext
    assert decrypted == b'refresh-token-secret'


def test_fernet_crypto_repr_does_not_expose_plaintext_or_secret() -> None:
    secret = Fernet.generate_key()
    crypto = FernetTokenCryptoProvider(secret=secret, key_id='google-token-key-v1')
    encrypted = crypto.encrypt_token('refresh-token-secret')

    combined_repr = '\n'.join([repr(crypto), repr(encrypted)])

    assert 'refresh-token-secret' not in combined_repr
    assert secret.decode('utf-8') not in combined_repr


def test_fernet_crypto_wrong_secret_cannot_decrypt() -> None:
    encrypted = FernetTokenCryptoProvider(
        secret=Fernet.generate_key(),
        key_id='google-token-key-v1',
    ).encrypt_token('refresh-token-secret')
    wrong_crypto = FernetTokenCryptoProvider(
        secret=Fernet.generate_key(),
        key_id='google-token-key-v1',
    )

    with pytest.raises(TokenCryptoError, match='token_ciphertext_invalid'):
        wrong_crypto.decrypt_token(encrypted)


def test_fernet_crypto_rejects_wrong_key_and_version() -> None:
    crypto = FernetTokenCryptoProvider(secret=Fernet.generate_key(), key_id='google-token-key-v1')
    encrypted = crypto.encrypt_token('refresh-token-secret')

    wrong_key = FernetTokenCryptoProvider(secret=Fernet.generate_key(), key_id='google-token-key-v2')
    wrong_version = FernetTokenCryptoProvider(
        secret=Fernet.generate_key(),
        key_id='google-token-key-v1',
        version=2,
    )

    with pytest.raises(TokenCryptoError, match='token_key_mismatch'):
        wrong_key.decrypt_token(encrypted)
    with pytest.raises(TokenCryptoError, match='token_version_mismatch'):
        wrong_version.decrypt_token(encrypted)


def test_deterministic_fake_provider_is_documented_as_tests_only() -> None:
    doc = ' '.join((DeterministicFakeTokenCryptoProvider.__doc__ or '').split())

    assert 'tests only' in doc
    assert 'not cryptographically secure' in doc


def test_token_crypto_has_no_google_or_network_imports() -> None:
    source = token_crypto.__loader__.get_source(token_crypto.__name__)  # type: ignore[union-attr]

    forbidden = ('googleapiclient', 'google.auth', 'requests', 'httpx', 'aiohttp', 'socket')

    assert source is not None
    assert not any(name in source for name in forbidden)


def test_env_examples_contain_only_token_crypto_secret_placeholders() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    for relative_path in ('.env.example', '.env.server.example'):
        content = (repo_root / relative_path).read_text(encoding='utf-8')

        assert 'GOOGLE_TOKEN_CRYPTO_SECRET=' in content
        assert 'gAAAAA' not in content
        assert 'refresh-token-secret' not in content
        assert 'fake-callback-refresh-token' not in content


def test_token_crypto_rejects_empty_plaintext() -> None:
    crypto = DeterministicFakeTokenCryptoProvider()

    with pytest.raises(TokenCryptoError, match='token_plaintext_required'):
        crypto.encrypt_token('')
