from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bot.services.google_integration_oauth import (
    GoogleIntegrationOAuthError,
    GoogleIntegrationTokenClient,
    OfficialGoogleIdentityVerifier,
)
from bot.services.google_integration_service import (
    GoogleBindingStatus,
    GoogleIntegrationError,
    GoogleIntegrationService,
    GoogleOAuthState,
)


class GoogleIntegrationCallbackError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoogleIntegrationCallbackPayload:
    state: str
    code: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class GoogleIntegrationCallbackResult:
    success: bool
    telegram_id: int | None = None
    workspace_id: str | None = None
    status: GoogleBindingStatus | None = None
    error_code: str | None = None


class GoogleIntegrationCallbackService:
    def __init__(
        self,
        *,
        integration: GoogleIntegrationService,
        tokens: GoogleIntegrationTokenClient,
        identities: OfficialGoogleIdentityVerifier,
        validate_context: Callable[[GoogleOAuthState], None],
    ) -> None:
        self._integration = integration
        self._tokens = tokens
        self._identities = identities
        self._validate_context = validate_context

    def handle(
        self, payload: GoogleIntegrationCallbackPayload
    ) -> GoogleIntegrationCallbackResult:
        raw_state = _bounded_required(payload.state, "state", 512)
        if payload.error:
            try:
                state = self._integration.reject_state(raw_state)
            except GoogleIntegrationError:
                return GoogleIntegrationCallbackResult(
                    success=False, error_code="oauth_state_invalid"
                )
            return GoogleIntegrationCallbackResult(
                success=False,
                telegram_id=state.telegram_id,
                workspace_id=state.workspace_id,
                error_code="oauth_provider_rejected",
            )
        try:
            state = self._integration.consume_state(raw_state)
        except GoogleIntegrationError as exc:
            return GoogleIntegrationCallbackResult(
                success=False, error_code=_safe_error(exc)
            )
        try:
            self._validate_context(state)
            code = _bounded_required(payload.code, "code", 4096)
            token = self._tokens.exchange_code(
                code=code,
                redirect_uri=state.redirect_uri,
                requested_scopes=state.requested_scopes,
            )
            if token.id_token is None:
                raise GoogleIntegrationOAuthError("oauth_id_token_required")
            identity = self._identities.verify(token.id_token)
            status = self._integration.save_verified_binding(
                state=state, identity=identity, token=token
            )
        except (GoogleIntegrationError, GoogleIntegrationOAuthError) as exc:
            error_code = _safe_error(exc)
            self._integration.mark_state_failed(state.state_id, error_code)
            return GoogleIntegrationCallbackResult(
                success=False,
                telegram_id=state.telegram_id,
                workspace_id=state.workspace_id,
                error_code=error_code,
            )
        except Exception:
            self._integration.mark_state_failed(
                state.state_id, "oauth_callback_failed"
            )
            return GoogleIntegrationCallbackResult(
                success=False,
                telegram_id=state.telegram_id,
                workspace_id=state.workspace_id,
                error_code="oauth_callback_failed",
            )
        return GoogleIntegrationCallbackResult(
            success=True,
            telegram_id=state.telegram_id,
            workspace_id=state.workspace_id,
            status=status,
        )


def _bounded_required(value: object, field: str, maximum: int) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or len(text) > maximum or any(c in text for c in "\r\n\x00"):
        raise GoogleIntegrationCallbackError(f"oauth_{field}_invalid")
    return text


def _safe_error(error: Exception) -> str:
    text = str(error).strip()
    if not text or len(text) > 80 or any(c in text for c in "\r\n"):
        return "oauth_callback_failed"
    return text
