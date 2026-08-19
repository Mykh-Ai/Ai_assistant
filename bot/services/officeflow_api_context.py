from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.services.access_control import AUTHORIZED_STATUS_ACTIVE, AccessControlService
from bot.services.api_session import ApiSessionError, ApiSessionRecord, ApiSessionService
from bot.services.principal_identity import PrincipalIdentityError, PrincipalIdentityService
from bot.services.workspace_context import (
    WorkspaceContext,
    WorkspaceContextError,
    WorkspaceContextService,
)


class OfficeFlowApiAuthorizationError(RuntimeError):
    pass


class OfficeFlowApiWorkspaceError(RuntimeError):
    pass


class OfficeFlowApiWorkspaceSelectionRequired(OfficeFlowApiWorkspaceError):
    pass


@dataclass(frozen=True)
class AuthenticatedOfficeFlowApiContext:
    session: ApiSessionRecord
    telegram_id: int


class OfficeFlowApiContextService:
    def __init__(
        self,
        db_path: Path,
        *,
        session_service: ApiSessionService | None = None,
    ) -> None:
        self._db_path = db_path
        self._sessions = session_service or ApiSessionService(db_path)
        self._principals = PrincipalIdentityService(db_path)
        self._access = AccessControlService(db_path)
        self._workspaces = WorkspaceContextService(db_path)

    def authenticate_access(
        self,
        raw_access_token: str,
    ) -> AuthenticatedOfficeFlowApiContext:
        try:
            session = self._sessions.authenticate_access(raw_access_token)
            telegram_id = self._principals.resolve_active_telegram_id(
                session.principal_id
            )
        except (ApiSessionError, PrincipalIdentityError) as exc:
            raise OfficeFlowApiAuthorizationError('api_unauthorized') from exc
        user = self._access.get_authorized_user(telegram_id)
        if user is None or user.status != AUTHORIZED_STATUS_ACTIVE:
            raise OfficeFlowApiAuthorizationError('api_unauthorized')
        try:
            self._sessions.touch_last_seen(session_id=session.session_id)
        except Exception as exc:
            raise OfficeFlowApiAuthorizationError('api_unauthorized') from exc
        return AuthenticatedOfficeFlowApiContext(
            session=session,
            telegram_id=telegram_id,
        )

    def list_accessible_workspaces(
        self,
        authenticated: AuthenticatedOfficeFlowApiContext,
    ) -> list[WorkspaceContext]:
        try:
            return self._workspaces.list_accessible_workspaces(
                authenticated.telegram_id
            )
        except WorkspaceContextError as exc:
            raise OfficeFlowApiAuthorizationError('api_unauthorized') from exc

    def resolve_read_workspace(
        self,
        authenticated: AuthenticatedOfficeFlowApiContext,
        requested_workspace_id: str | None,
    ) -> WorkspaceContext:
        contexts = self.list_accessible_workspaces(authenticated)
        if requested_workspace_id is not None:
            normalized = _workspace_id(requested_workspace_id)
            for context in contexts:
                if context.workspace_id == normalized:
                    return context
            raise OfficeFlowApiWorkspaceError('workspace_not_found')
        if len(contexts) == 1:
            return contexts[0]
        if len(contexts) > 1:
            raise OfficeFlowApiWorkspaceSelectionRequired(
                'workspace_selection_required'
            )
        raise OfficeFlowApiWorkspaceError('workspace_not_found')


def _workspace_id(value: str) -> str:
    normalized = str(value).strip()
    if (
        not normalized
        or len(normalized) > 128
        or any(c in normalized for c in '\r\n\x00')
    ):
        raise OfficeFlowApiWorkspaceError('workspace_not_found')
    return normalized
