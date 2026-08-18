from __future__ import annotations

import pytest
from google.auth.exceptions import RefreshError, TransportError

from bot.services.gmail_readonly_adapter import (
    GmailReadonlyNeedsReauth,
    GmailReadonlyRetryableError,
)
from bot.services.google_api_gmail_transport import GoogleAPIGmailReadonlyTransport


class Request:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    def execute(self):
        if self.error is not None:
            raise self.error
        return self.response


class Resource:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.error: Exception | None = None

    def users(self):
        return self

    def messages(self):
        return self

    def attachments(self):
        return self

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        return Request({"messages": [{"id": "m1"}]}, self.error)

    def get(self, **kwargs):
        self.calls.append(("get", kwargs))
        response = {"data": "YQ"} if "messageId" in kwargs else {"id": "m1"}
        return Request(response, self.error)


class ProviderError(Exception):
    def __init__(self, status: int) -> None:
        self.resp = type("Response", (), {"status": status})()


def test_transport_exposes_only_read_operations() -> None:
    resource = Resource()
    transport = GoogleAPIGmailReadonlyTransport(
        access_token="a",
        refresh_token="r",
        client_id="c",
        client_secret="s",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
        service=resource,
    )

    assert transport.list_messages(
        query="has:attachment", page_token=None, max_results=10
    ) == (("m1",), None)
    assert transport.get_message("m1") == {"id": "m1"}
    assert transport.get_attachment("m1", "a1") == "YQ"
    assert not hasattr(transport, "send_message")
    assert not hasattr(transport, "modify_message")
    assert not hasattr(transport, "delete_message")
    assert resource.calls[0][1]["userId"] == "me"


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, GmailReadonlyNeedsReauth),
        (403, GmailReadonlyNeedsReauth),
        (429, GmailReadonlyRetryableError),
        (503, GmailReadonlyRetryableError),
    ],
)
def test_transport_maps_provider_status_without_raw_error(
    status: int, error_type: type[Exception]
) -> None:
    resource = Resource()
    resource.error = ProviderError(status)
    transport = GoogleAPIGmailReadonlyTransport(
        access_token="a",
        refresh_token="r",
        client_id="c",
        client_secret="s",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
        service=resource,
    )

    with pytest.raises(error_type):
        transport.list_messages(
            query="has:attachment", page_token=None, max_results=10
        )


def test_transport_maps_refresh_invalid_grant_to_needs_reauth() -> None:
    resource = Resource()
    resource.error = RefreshError(
        "invalid_grant: Token has been expired or revoked.",
        {"error": "invalid_grant", "error_description": "sensitive provider text"},
        retryable=False,
    )
    transport = GoogleAPIGmailReadonlyTransport(
        access_token="a",
        refresh_token="r",
        client_id="c",
        client_secret="s",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
        service=resource,
    )

    with pytest.raises(GmailReadonlyNeedsReauth, match="^gmail_needs_reauth$"):
        transport.list_messages(
            query="has:attachment", page_token=None, max_results=10
        )


@pytest.mark.parametrize(
    "error",
    [
        RefreshError(
            "temporarily unavailable",
            {"error": "temporarily_unavailable"},
            retryable=True,
        ),
        TransportError("network unavailable"),
    ],
)
def test_transport_maps_refresh_transport_failures_to_retryable(
    error: Exception,
) -> None:
    resource = Resource()
    resource.error = error
    transport = GoogleAPIGmailReadonlyTransport(
        access_token="a",
        refresh_token="r",
        client_id="c",
        client_secret="s",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
        service=resource,
    )

    with pytest.raises(
        GmailReadonlyRetryableError, match="^gmail_provider_retryable$"
    ):
        transport.list_messages(
            query="has:attachment", page_token=None, max_results=10
        )
