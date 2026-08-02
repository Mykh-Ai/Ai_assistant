from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from bot.google_integration_callback_app import (
    INTERNAL_CALLBACK_PATH,
    PROXY_SECRET_HEADER,
    create_google_integration_callback_app,
    handle_google_integration_callback,
    handle_google_integration_callback_relay,
)
from bot.services.google_integration_callback_service import (
    GoogleIntegrationCallbackPayload,
    GoogleIntegrationCallbackResult,
)


SECRET = "relay-secret-" + ("s" * 32)


class DummyCallbackService:
    def __init__(self, *, success: bool = True) -> None:
        self.success = success
        self.payloads: list[GoogleIntegrationCallbackPayload] = []

    def handle(
        self, payload: GoogleIntegrationCallbackPayload
    ) -> GoogleIntegrationCallbackResult:
        self.payloads.append(payload)
        return GoogleIntegrationCallbackResult(
            success=self.success,
            telegram_id=42,
            workspace_id="workspace",
        )


def _app(service: DummyCallbackService) -> web.Application:
    return create_google_integration_callback_app(
        callback_service=service,  # type: ignore[arg-type]
        proxy_secret=SECRET,
    )


def _signed_query(
    *,
    state: str = "state-token",
    code: str | None = "authorization-code",
    error: str | None = None,
    issued_at: int | None = None,
) -> str:
    body: dict[str, object] = {
        "state": state,
        "issued_at": int(time.time()) if issued_at is None else issued_at,
    }
    if code is not None:
        body["code"] = code
    if error is not None:
        body["error"] = error
    raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    payload = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(
        SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode({"payload": payload, "signature": signature})


def test_signed_browser_relay_is_verified_and_returns_safe_html() -> None:
    service = DummyCallbackService()
    request = make_mocked_request(
        "GET",
        f"{INTERNAL_CALLBACK_PATH}?{_signed_query()}",
        app=_app(service),
    )

    response = asyncio.run(handle_google_integration_callback_relay(request))

    assert response.status == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert service.payloads == [
        GoogleIntegrationCallbackPayload(
            state="state-token",
            code="authorization-code",
        )
    ]
    browser = response.text
    assert "state-token" not in browser
    assert "authorization-code" not in browser
    assert SECRET not in browser


def test_signed_browser_relay_rejects_tampering_before_callback() -> None:
    service = DummyCallbackService()
    query = _signed_query().replace("signature=", "signature=0", 1)
    request = make_mocked_request(
        "GET",
        f"{INTERNAL_CALLBACK_PATH}?{query}",
        app=_app(service),
    )

    try:
        asyncio.run(handle_google_integration_callback_relay(request))
    except web.HTTPUnauthorized:
        pass
    else:
        raise AssertionError("tampered relay must be unauthorized")

    assert service.payloads == []


def test_signed_browser_relay_rejects_expired_payload() -> None:
    service = DummyCallbackService()
    request = make_mocked_request(
        "GET",
        f"{INTERNAL_CALLBACK_PATH}?{_signed_query(issued_at=int(time.time()) - 301)}",
        app=_app(service),
    )

    try:
        asyncio.run(handle_google_integration_callback_relay(request))
    except web.HTTPUnauthorized:
        pass
    else:
        raise AssertionError("expired relay must be unauthorized")

    assert service.payloads == []


def test_internal_post_remains_secret_bound() -> None:
    service = DummyCallbackService()
    app = _app(service)
    unauthorized = make_mocked_request(
        "POST",
        INTERNAL_CALLBACK_PATH,
        app=app,
    )
    unauthorized._read_bytes = json.dumps(
        {"state": "state-token", "code": "authorization-code"}
    ).encode()

    try:
        asyncio.run(handle_google_integration_callback(unauthorized))
    except web.HTTPUnauthorized:
        pass
    else:
        raise AssertionError("missing proxy secret must be unauthorized")

    request = make_mocked_request(
        "POST",
        INTERNAL_CALLBACK_PATH,
        headers={
            PROXY_SECRET_HEADER: SECRET,
            "Content-Type": "application/json",
        },
        app=app,
    )
    request._read_bytes = json.dumps(
        {"state": "state-token", "code": "authorization-code"}
    ).encode()

    response = asyncio.run(handle_google_integration_callback(request))

    assert response.status == 200
    assert service.payloads == [
        GoogleIntegrationCallbackPayload(
            state="state-token",
            code="authorization-code",
        )
    ]