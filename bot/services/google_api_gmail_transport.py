from __future__ import annotations

from typing import Any

from bot.services.gmail_readonly_adapter import (
    GmailReadonlyError,
    GmailReadonlyNeedsReauth,
    GmailReadonlyRetryableError,
)


class GoogleAPIGmailReadonlyTransport:
    """Narrow Gmail API transport; deliberately exposes no mutation methods."""

    def __init__(
        self,
        *,
        access_token: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        scopes: tuple[str, ...],
        service: object | None = None,
    ) -> None:
        if service is None:
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
            except ImportError:
                raise GmailReadonlyError("gmail_dependency_missing") from None
            credentials = Credentials(
                token=_required(access_token),
                refresh_token=_required(refresh_token),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=_required(client_id),
                client_secret=_required(client_secret),
                scopes=list(scopes),
            )
            service = build(
                "gmail", "v1", credentials=credentials, cache_discovery=False
            )
        self._service = service

    def list_messages(
        self, *, query: str, page_token: str | None, max_results: int
    ) -> tuple[tuple[str, ...], str | None]:
        try:
            response = (
                self._service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    pageToken=page_token,
                    maxResults=max_results,
                    fields="messages/id,nextPageToken",
                )
                .execute()
            )
        except Exception as exc:
            _raise_transport(exc)
        messages = response.get("messages", []) if isinstance(response, dict) else []
        ids = tuple(
            str(item["id"])
            for item in messages
            if isinstance(item, dict) and item.get("id")
        )
        next_token = response.get("nextPageToken") if isinstance(response, dict) else None
        return ids, str(next_token) if next_token else None

    def get_message(self, message_id: str) -> dict[str, object]:
        try:
            response = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=_required(message_id),
                    format="full",
                    fields=(
                        "id,threadId,internalDate,"
                        "payload(partId,mimeType,filename,headers(name,value),"
                        "body(attachmentId,size,data),"
                        "parts(partId,mimeType,filename,headers(name,value),"
                        "body(attachmentId,size,data),parts))"
                    ),
                )
                .execute()
            )
        except Exception as exc:
            _raise_transport(exc)
        if not isinstance(response, dict):
            raise GmailReadonlyError("gmail_message_invalid")
        return response

    def get_attachment(self, message_id: str, attachment_id: str) -> str:
        try:
            response = (
                self._service.users()
                .messages()
                .attachments()
                .get(
                    userId="me",
                    messageId=_required(message_id),
                    id=_required(attachment_id),
                )
                .execute()
            )
        except Exception as exc:
            _raise_transport(exc)
        data = response.get("data") if isinstance(response, dict) else None
        if not isinstance(data, str) or not data:
            raise GmailReadonlyError("gmail_attachment_empty")
        return data


def _raise_transport(error: Exception) -> None:
    status = getattr(getattr(error, "resp", None), "status", None)
    if status in {401, 403}:
        raise GmailReadonlyNeedsReauth("gmail_needs_reauth") from None
    if status in {408, 429} or (isinstance(status, int) and status >= 500):
        raise GmailReadonlyRetryableError("gmail_provider_retryable") from None
    raise GmailReadonlyError("gmail_provider_failed") from None


def _required(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise GmailReadonlyError("gmail_credential_required")
    return text
