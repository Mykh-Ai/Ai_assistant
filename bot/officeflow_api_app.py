from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
import os
from pathlib import Path
from typing import Awaitable, Callable

from aiohttp import web

from bot.services.api_enrollment import ApiEnrollmentError, ApiEnrollmentService
from bot.services.api_session import ApiSessionError, ApiSessionService
from bot.services.db import init_db
from bot.services.officeflow_api_context import (
    AuthenticatedOfficeFlowApiContext,
    OfficeFlowApiAuthorizationError,
    OfficeFlowApiContextService,
    OfficeFlowApiWorkspaceError,
    OfficeFlowApiWorkspaceSelectionRequired,
)
from bot.services.officeflow_read_service import (
    OfficeFlowReadNotFound,
    OfficeFlowReadService,
)


logger = logging.getLogger(__name__)
MAX_REQUEST_BODY_BYTES = 16 * 1024
DEFAULT_INVOICE_LIMIT = 50

ENROLLMENT_KEY = web.AppKey('officeflow_api_enrollment', ApiEnrollmentService)
SESSION_KEY = web.AppKey('officeflow_api_session', ApiSessionService)
CONTEXT_KEY = web.AppKey('officeflow_api_context', OfficeFlowApiContextService)
READ_KEY = web.AppKey('officeflow_api_read', OfficeFlowReadService)


@dataclass(frozen=True)
class OfficeFlowApiConfig:
    db_path: Path
    storage_dir: Path
    host: str = '127.0.0.1'
    port: int = 8081


def load_officeflow_api_config() -> OfficeFlowApiConfig:
    host = os.getenv('OFFICEFLOW_API_HOST', '127.0.0.1').strip()
    if not host or len(host) > 255 or any(c in host for c in '\r\n\x00'):
        raise RuntimeError('officeflow_api_host_invalid')
    raw_port = os.getenv('OFFICEFLOW_API_PORT', '8081').strip()
    try:
        port = int(raw_port)
    except ValueError as exc:
        raise RuntimeError('officeflow_api_port_invalid') from exc
    if port < 1 or port > 65535:
        raise RuntimeError('officeflow_api_port_invalid')
    return OfficeFlowApiConfig(
        db_path=Path(os.getenv('DB_PATH', 'storage/fakturabot.db')).resolve(),
        storage_dir=Path(os.getenv('STORAGE_DIR', 'storage')).resolve(),
        host=host,
        port=port,
    )


def create_officeflow_api_app(
    *,
    db_path: Path,
    storage_dir: Path,
    enrollment_service: ApiEnrollmentService | None = None,
    session_service: ApiSessionService | None = None,
    context_service: OfficeFlowApiContextService | None = None,
    read_service: OfficeFlowReadService | None = None,
) -> web.Application:
    sessions = session_service or ApiSessionService(db_path)
    app = web.Application(
        client_max_size=MAX_REQUEST_BODY_BYTES,
        middlewares=[_bounded_error_middleware],
    )
    app[SESSION_KEY] = sessions
    app[ENROLLMENT_KEY] = enrollment_service or ApiEnrollmentService(
        db_path,
        session_service=sessions,
    )
    app[CONTEXT_KEY] = context_service or OfficeFlowApiContextService(
        db_path,
        session_service=sessions,
    )
    app[READ_KEY] = read_service or OfficeFlowReadService(db_path, storage_dir)

    app.router.add_post('/v1/enrollment/exchange', _exchange_enrollment)
    app.router.add_post('/v1/session/refresh', _refresh_session)
    app.router.add_delete('/v1/session', _delete_session)
    app.router.add_get('/v1/session', _get_session, allow_head=False)
    app.router.add_get('/v1/workspaces', _get_workspaces, allow_head=False)
    app.router.add_get('/v1/invoices', _get_invoices, allow_head=False)
    app.router.add_get('/v1/invoices/{invoice_id}', _get_invoice, allow_head=False)
    app.router.add_get(
        '/v1/invoices/{invoice_id}/pdf',
        _get_invoice_pdf,
        allow_head=False,
    )
    app.router.add_get('/v1/contacts', _get_contacts, allow_head=False)
    return app


@web.middleware
async def _bounded_error_middleware(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    try:
        response = await handler(request)
    except OfficeFlowApiWorkspaceSelectionRequired:
        response = _error_response(409, 'workspace_selection_required')
    except OfficeFlowApiWorkspaceError:
        response = _error_response(404, 'workspace_not_found')
    except OfficeFlowReadNotFound:
        response = _error_response(404, 'not_found')
    except (OfficeFlowApiAuthorizationError, ApiSessionError):
        response = _error_response(401, 'unauthorized')
    except ApiEnrollmentError:
        response = _error_response(401, 'invalid_enrollment')
    except web.HTTPRequestEntityTooLarge:
        response = _error_response(413, 'request_too_large')
    except web.HTTPException as exc:
        code = {
            400: 'invalid_request',
            404: 'not_found',
            405: 'method_not_allowed',
            415: 'unsupported_media_type',
        }.get(exc.status, 'request_failed')
        response = _error_response(exc.status, code)
        if exc.status == 405 and exc.headers.get('Allow'):
            response.headers['Allow'] = exc.headers['Allow']
    except (ValueError, TypeError):
        response = _error_response(400, 'invalid_request')
    except Exception:
        logger.error('officeflow_api_request_failed error_code=internal_error')
        response = _error_response(500, 'internal_error')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


async def _exchange_enrollment(request: web.Request) -> web.Response:
    body = await _json_object(
        request,
        required={'enrollment_secret'},
        optional={'device_label'},
    )
    credentials = request.app[ENROLLMENT_KEY].exchange(
        _body_text(body, 'enrollment_secret', maximum=160),
        device_label=_optional_body_text(body, 'device_label', maximum=80),
    )
    return web.json_response({'session': asdict(credentials)})


async def _refresh_session(request: web.Request) -> web.Response:
    body = await _json_object(request, required={'refresh_token'})
    credentials = request.app[SESSION_KEY].rotate_refresh(
        _body_text(body, 'refresh_token', maximum=160)
    )
    return web.json_response({'session': asdict(credentials)})


async def _delete_session(request: web.Request) -> web.Response:
    access_token = _bearer_token(request)
    request.app[CONTEXT_KEY].authenticate_access(access_token)
    request.app[SESSION_KEY].revoke_access(access_token)
    return web.Response(status=204)


async def _get_session(request: web.Request) -> web.Response:
    _require_query(request, set())
    authenticated = _authenticate(request)
    session = authenticated.session
    return web.json_response(
        {
            'session': {
                'device_label': session.device_label,
                'created_at': session.created_at,
                'last_seen_at': session.last_seen_at,
                'access_expires_at': session.access_expires_at,
                'refresh_expires_at': session.refresh_expires_at,
            }
        }
    )


async def _get_workspaces(request: web.Request) -> web.Response:
    _require_query(request, set())
    authenticated = _authenticate(request)
    contexts = request.app[CONTEXT_KEY].list_accessible_workspaces(authenticated)
    return web.json_response(
        {
            'workspaces': [
                {
                    'workspace_id': context.workspace_id,
                    'display_name': context.workspace_display_name,
                    'role': context.membership_role,
                }
                for context in contexts
            ]
        }
    )


async def _get_invoices(request: web.Request) -> web.Response:
    _require_query(request, {'workspace_id', 'limit', 'offset'})
    authenticated, workspace = _authenticate_workspace(request)
    del authenticated
    limit = _query_int(request, 'limit', default=DEFAULT_INVOICE_LIMIT, minimum=1, maximum=100)
    offset = _query_int(request, 'offset', default=0, minimum=0, maximum=100_000)
    invoices = request.app[READ_KEY].list_invoices(
        workspace,
        limit=limit,
        offset=offset,
    )
    return web.json_response(
        {
            'workspace_id': workspace.workspace_id,
            'invoices': invoices,
            'limit': limit,
            'offset': offset,
        }
    )


async def _get_invoice(request: web.Request) -> web.Response:
    _require_query(request, {'workspace_id'})
    _, workspace = _authenticate_workspace(request)
    invoice = request.app[READ_KEY].get_invoice_detail(
        workspace,
        _invoice_id(request),
    )
    return web.json_response(
        {'workspace_id': workspace.workspace_id, 'invoice': invoice}
    )


async def _get_invoice_pdf(request: web.Request) -> web.StreamResponse:
    _require_query(request, {'workspace_id'})
    _, workspace = _authenticate_workspace(request)
    path, filename = request.app[READ_KEY].resolve_invoice_pdf(
        workspace,
        _invoice_id(request),
    )
    return web.FileResponse(
        path,
        headers={
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename="{filename}"',
        },
    )


async def _get_contacts(request: web.Request) -> web.Response:
    _require_query(request, {'workspace_id'})
    _, workspace = _authenticate_workspace(request)
    return web.json_response(
        {
            'workspace_id': workspace.workspace_id,
            'contacts': request.app[READ_KEY].list_contacts(workspace),
        }
    )


def _authenticate(request: web.Request) -> AuthenticatedOfficeFlowApiContext:
    return request.app[CONTEXT_KEY].authenticate_access(_bearer_token(request))


def _authenticate_workspace(request: web.Request):
    authenticated = _authenticate(request)
    workspace = request.app[CONTEXT_KEY].resolve_read_workspace(
        authenticated,
        request.query.get('workspace_id'),
    )
    return authenticated, workspace


def _bearer_token(request: web.Request) -> str:
    value = request.headers.get('Authorization', '')
    if len(value) > 192 or not value.startswith('Bearer '):
        raise OfficeFlowApiAuthorizationError('api_unauthorized')
    token = value[7:]
    if not token or token != token.strip() or ' ' in token:
        raise OfficeFlowApiAuthorizationError('api_unauthorized')
    return token


async def _json_object(
    request: web.Request,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> dict[str, object]:
    if request.content_type != 'application/json':
        raise web.HTTPUnsupportedMediaType()
    try:
        body = await request.json()
    except web.HTTPRequestEntityTooLarge:
        raise
    except Exception:
        raise web.HTTPBadRequest() from None
    allowed = required | (optional or set())
    if not isinstance(body, dict) or set(body) != required | (set(body) & (optional or set())):
        raise web.HTTPBadRequest()
    if set(body) - allowed:
        raise web.HTTPBadRequest()
    return body


def _body_text(body: dict[str, object], key: str, *, maximum: int) -> str:
    value = body.get(key)
    if not isinstance(value, str):
        raise web.HTTPBadRequest()
    text = value.strip()
    if not text or len(text) > maximum or any(c in text for c in '\r\n\x00'):
        raise web.HTTPBadRequest()
    return text


def _optional_body_text(
    body: dict[str, object],
    key: str,
    *,
    maximum: int,
) -> str | None:
    if key not in body or body[key] is None:
        return None
    return _body_text(body, key, maximum=maximum)


def _require_query(request: web.Request, allowed: set[str]) -> None:
    if set(request.query) - allowed:
        raise web.HTTPBadRequest()
    for key in request.query:
        if len(request.query.getall(key)) != 1:
            raise web.HTTPBadRequest()


def _query_int(
    request: web.Request,
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if key not in request.query:
        return default
    raw = request.query[key]
    if not raw.isascii() or not raw.isdigit() or len(raw) > 6:
        raise web.HTTPBadRequest()
    value = int(raw)
    if value < minimum or value > maximum:
        raise web.HTTPBadRequest()
    return value


def _invoice_id(request: web.Request) -> int:
    raw = request.match_info['invoice_id']
    if not raw.isascii() or not raw.isdigit() or len(raw) > 19:
        raise OfficeFlowReadNotFound('invoice_not_found')
    value = int(raw)
    if value < 1 or value > 9_223_372_036_854_775_807:
        raise OfficeFlowReadNotFound('invoice_not_found')
    return value


def _error_response(status: int, code: str) -> web.Response:
    return web.json_response({'error': {'code': code}}, status=status)


def main() -> None:
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
    config = load_officeflow_api_config()
    init_db(config.db_path)
    web.run_app(
        create_officeflow_api_app(
            db_path=config.db_path,
            storage_dir=config.storage_dir,
        ),
        host=config.host,
        port=config.port,
    )


if __name__ == '__main__':
    main()
