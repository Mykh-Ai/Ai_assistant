from __future__ import annotations

import hmac
import logging
from typing import Awaitable, Callable

from aiohttp import web

from bot.services.google_integration_callback_service import (
    GoogleIntegrationCallbackPayload,
    GoogleIntegrationCallbackService,
)


logger = logging.getLogger(__name__)
INTERNAL_CALLBACK_PATH = "/internal/oauth/google/integration/callback"
MAX_CALLBACK_BODY_BYTES = 8 * 1024
PROXY_SECRET_HEADER = "X-ZevsFlow-Callback-Secret"

CALLBACK_SERVICE_KEY = web.AppKey(
    "google_integration_callback_service", GoogleIntegrationCallbackService
)
PROXY_SECRET_KEY = web.AppKey("google_integration_callback_proxy_secret", str)
NOTIFY_KEY = web.AppKey(
    "google_integration_callback_notify",
    Callable[[int, bool], Awaitable[None]],
)


def create_google_integration_callback_app(
    *,
    callback_service: GoogleIntegrationCallbackService,
    proxy_secret: str,
    notify: Callable[[int, bool], Awaitable[None]] | None = None,
) -> web.Application:
    secret = proxy_secret.strip()
    if len(secret) < 32:
        raise ValueError("google_callback_proxy_secret_too_short")
    app = web.Application(client_max_size=MAX_CALLBACK_BODY_BYTES)
    app[CALLBACK_SERVICE_KEY] = callback_service
    app[PROXY_SECRET_KEY] = secret
    if notify is not None:
        app[NOTIFY_KEY] = notify
    app.router.add_post(INTERNAL_CALLBACK_PATH, handle_google_integration_callback)
    return app


async def handle_google_integration_callback(request: web.Request) -> web.Response:
    supplied = request.headers.get(PROXY_SECRET_HEADER, "")
    expected = request.app[PROXY_SECRET_KEY]
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        logger.warning("google_integration_callback_rejected error_code=proxy_unauthorized")
        raise web.HTTPUnauthorized()
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest() from None
    if not isinstance(body, dict) or set(body) - {"state", "code", "error"}:
        raise web.HTTPBadRequest()
    try:
        payload = GoogleIntegrationCallbackPayload(
            state=str(body.get("state", "")),
            code=_optional_body_text(body.get("code"), 4096),
            error=_optional_body_text(body.get("error"), 128),
        )
        result = request.app[CALLBACK_SERVICE_KEY].handle(payload)
    except Exception:
        logger.warning(
            "google_integration_callback_failed error_code=callback_payload_invalid"
        )
        raise web.HTTPBadRequest() from None
    notify = request.app.get(NOTIFY_KEY)
    if notify is not None and result.telegram_id is not None:
        try:
            await notify(result.telegram_id, result.success)
        except Exception:
            logger.warning(
                "google_integration_callback_notification_failed success=%s",
                result.success,
            )
    return web.json_response(
        {"success": result.success},
        status=200 if result.success else 400,
    )


def _optional_body_text(value: object, maximum: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) > maximum or any(c in text for c in "\r\n\x00"):
        raise ValueError("callback_value_invalid")
    return text or None
