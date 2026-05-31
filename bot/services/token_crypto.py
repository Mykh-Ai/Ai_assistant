from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - covered by deployment dependency checks
    Fernet = None  # type: ignore[assignment]
    InvalidToken = Exception  # type: ignore[assignment]


class TokenCryptoError(ValueError):
    pass


@dataclass(frozen=True)
class EncryptedToken:
    ciphertext: bytes
    key_id: str
    version: int = 1


class TokenCryptoProvider(Protocol):
    def encrypt_token(self, plaintext: bytes | str) -> EncryptedToken:
        """Encrypt token material for persistence."""

    def decrypt_token(self, encrypted: EncryptedToken) -> bytes:
        """Decrypt token material for provider use."""


class UnconfiguredTokenCryptoProvider:
    """Production placeholder until a deployment secret/KMS is explicitly wired."""

    def encrypt_token(self, plaintext: bytes | str) -> EncryptedToken:
        raise TokenCryptoError('token_crypto_not_configured')

    def decrypt_token(self, encrypted: EncryptedToken) -> bytes:
        raise TokenCryptoError('token_crypto_not_configured')


class FernetTokenCryptoProvider:
    """Production-capable token crypto using authenticated Fernet encryption."""

    def __init__(
        self,
        *,
        secret: bytes | str | None,
        key_id: str,
        version: int = 1,
    ) -> None:
        if Fernet is None:
            raise TokenCryptoError('token_crypto_dependency_missing')
        self._key_id = _required_text(key_id, 'key_id')
        if version <= 0:
            raise TokenCryptoError('token_version_must_be_positive')
        self._version = version
        secret_bytes = _secret_bytes(secret)
        try:
            self._fernet = Fernet(secret_bytes)
        except Exception:
            raise TokenCryptoError('token_crypto_secret_invalid') from None

    def encrypt_token(self, plaintext: bytes | str) -> EncryptedToken:
        plaintext_bytes = _plaintext_bytes(plaintext)
        return EncryptedToken(
            ciphertext=self._fernet.encrypt(plaintext_bytes),
            key_id=self._key_id,
            version=self._version,
        )

    def decrypt_token(self, encrypted: EncryptedToken) -> bytes:
        if encrypted.key_id != self._key_id:
            raise TokenCryptoError('token_key_mismatch')
        if encrypted.version != self._version:
            raise TokenCryptoError('token_version_mismatch')
        try:
            return self._fernet.decrypt(encrypted.ciphertext)
        except InvalidToken:
            raise TokenCryptoError('token_ciphertext_invalid') from None


class DeterministicFakeTokenCryptoProvider:
    """Deterministic non-production crypto for tests only.

    It deliberately avoids returning plaintext-shaped ciphertext, but it is not
    cryptographically secure and must not be used for real credentials.
    """

    def __init__(self, *, key_id: str = 'fake-test-key', version: int = 1) -> None:
        self._key_id = _required_text(key_id, 'key_id')
        if version <= 0:
            raise TokenCryptoError('token_version_must_be_positive')
        self._version = version

    def encrypt_token(self, plaintext: bytes | str) -> EncryptedToken:
        plaintext_bytes = _plaintext_bytes(plaintext)
        return EncryptedToken(
            ciphertext=b'fake-token-v1:' + plaintext_bytes[::-1],
            key_id=self._key_id,
            version=self._version,
        )

    def decrypt_token(self, encrypted: EncryptedToken) -> bytes:
        if encrypted.key_id != self._key_id:
            raise TokenCryptoError('token_key_mismatch')
        if encrypted.version != self._version:
            raise TokenCryptoError('token_version_mismatch')
        prefix = b'fake-token-v1:'
        if not encrypted.ciphertext.startswith(prefix):
            raise TokenCryptoError('token_ciphertext_invalid')
        return encrypted.ciphertext[len(prefix):][::-1]


def _plaintext_bytes(value: bytes | str) -> bytes:
    if isinstance(value, str):
        value = value.encode('utf-8')
    if not value:
        raise TokenCryptoError('token_plaintext_required')
    return value


def _secret_bytes(value: bytes | str | None) -> bytes:
    if value is None:
        raise TokenCryptoError('token_crypto_secret_required')
    if isinstance(value, str):
        value = value.strip().encode('utf-8')
    if not value:
        raise TokenCryptoError('token_crypto_secret_required')
    return value


def _required_text(value: object, field_name: str) -> str:
    text = str(value).strip() if value is not None else ''
    if not text:
        raise TokenCryptoError(f'{field_name}_required')
    return text
