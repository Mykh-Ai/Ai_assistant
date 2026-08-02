from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from typing import Awaitable, Callable

from aiohttp import web

from bot.services.google_integration_callback_service import (
    GoogleIntegrationCallbackPayload,
    GoogleIntegrationCallbackService,
)


logger = logging.getLogger(__name__)
INTERNAL_CALLBACK_PATH = "/internal/oauth/google/integration/callback"
MAX_CALLBACK_BODY_BYTES = 8 * 1024
MAX_RELAY_PAYLOAD_LENGTH = 8 * 1024
RELAY_MAX_AGE_SECONDS = 5 * 60
RELAY_MAX_FUTURE_SKEW_SECONDS = 60
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
    app.router.add_get(INTERNAL_CALLBACK_PATH, handle_google_integration_callback_relay)
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
    except Exception:
        logger.warning(
            "google_integration_callback_failed error_code=callback_payload_invalid"
        )
        raise web.HTTPBadRequest() from None
    return await _complete_callback(request, payload, browser_response=False)


async def handle_google_integration_callback_relay(
    request: web.Request,
) -> web.Response:
    payload = _verified_relay_payload(request)
    return await _complete_callback(request, payload, browser_response=True)


async def _complete_callback(
    request: web.Request,
    payload: GoogleIntegrationCallbackPayload,
    *,
    browser_response: bool,
) -> web.Response:
    try:
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
    status = 200 if result.success else 400
    if not browser_response:
        return web.json_response({"success": result.success}, status=status)
    return _browser_response(result.success, status)


def _verified_relay_payload(request: web.Request) -> GoogleIntegrationCallbackPayload:
    if set(request.query) != {"payload", "signature"}:
        raise web.HTTPBadRequest()
    if any(len(request.query.getall(name)) != 1 for name in ("payload", "signature")):
        raise web.HTTPBadRequest()
    encoded = request.query["payload"].strip()
    supplied_signature = request.query["signature"].strip().lower()
    if (
        not encoded
        or len(encoded) > MAX_RELAY_PAYLOAD_LENGTH
        or len(supplied_signature) != 64
        or any(character not in "0123456789abcdef" for character in supplied_signature)
    ):
        raise web.HTTPUnauthorized()
    expected_signature = hmac.new(
        request.app[PROXY_SECRET_KEY].encode(),
        encoded.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        logger.warning("google_integration_callback_rejected error_code=relay_unauthorized")
        raise web.HTTPUnauthorized()
    try:
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        )
        body = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        raise web.HTTPBadRequest() from None
    allowed = {"state", "code", "error", "issued_at"}
    if not isinstance(body, dict) or set(body) - allowed:
        raise web.HTTPBadRequest()
    issued_at = body.get("issued_at")
    if isinstance(issued_at, bool) or not isinstance(issued_at, int):
        raise web.HTTPBadRequest()
    age = int(time.time()) - issued_at
    if age > RELAY_MAX_AGE_SECONDS or age < -RELAY_MAX_FUTURE_SKEW_SECONDS:
        raise web.HTTPUnauthorized()
    code = _optional_body_text(body.get("code"), 4096)
    error = _optional_body_text(body.get("error"), 128)
    if bool(code) == bool(error):
        raise web.HTTPBadRequest()
    return GoogleIntegrationCallbackPayload(
        state=str(body.get("state", "")),
        code=code,
        error=error,
    )


def _browser_response(success: bool, status: int) -> web.Response:
    title = "Pripojenie bolo dokončené" if success else "Pripojenie sa nepodarilo"
    message = (
        "Google účet bol bezpečne spracovaný. Môžete sa vrátiť do Telegramu."
        if success
        else "Požiadavku nebolo možné dokončiť. Vráťte sa do Telegramu a skúste pripojenie znova."
    )
    body = (
        '<!doctype html><html lang="sk"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        f"<title>{title} | ZevsFlow</title></head><body><main><h1>{title}</h1>"
        f"<p>{message}</p></main></body></html>"
    )
    return web.Response(
        text=body,
        status=status,
        content_type="text/html",
        charset="utf-8",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


def _optional_body_text(value: object, maximum: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) > maximum or any(c in text for c in "\r\n\x00"):
        raise ValueError("callback_value_invalid")
    return text or None
