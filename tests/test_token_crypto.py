from __future__ import annotations

import pytest

from bot.services.token_crypto import (
    DeterministicFakeTokenCryptoProvider,
    EncryptedToken,
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


def test_token_crypto_rejects_empty_plaintext() -> None:
    crypto = DeterministicFakeTokenCryptoProvider()

    with pytest.raises(TokenCryptoError, match='token_plaintext_required'):
        crypto.encrypt_token('')
