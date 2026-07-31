from __future__ import annotations

from dataclasses import dataclass, field
import base64
from typing import Iterable, Protocol


MAX_MIME_PARTS = 200
MAX_FILENAME_LENGTH = 255
MAX_INLINE_ENCODED_BYTES = 20 * 1024 * 1024


class GmailReadonlyError(RuntimeError):
    pass


class GmailReadonlyRetryableError(GmailReadonlyError):
    pass


class GmailReadonlyNeedsReauth(GmailReadonlyError):
    pass


class GmailReadonlyTransport(Protocol):
    def list_messages(
        self, *, query: str, page_token: str | None, max_results: int
    ) -> tuple[tuple[str, ...], str | None]:
        ...

    def get_message(self, message_id: str) -> dict[str, object]:
        ...

    def get_attachment(self, message_id: str, attachment_id: str) -> str:
        ...


@dataclass(frozen=True)
class GmailAttachmentCandidate:
    message_id: str
    thread_id: str | None
    source_attachment_key: str
    gmail_attachment_id: str | None
    mime_part_id: str
    filename: str
    mime_type: str
    declared_size: int | None
    sender: str | None
    subject: str | None
    internal_date: str | None
    _inline_data: str | None = field(default=None, repr=False)


class GmailReadonlyAdapter:
    """Read-only Gmail operations over an injected transport."""

    def __init__(
        self,
        transport: GmailReadonlyTransport,
        *,
        trusted_query: str,
        batch_size: int,
        max_pages: int = 10,
    ) -> None:
        self._transport = transport
        self._query = trusted_query.strip()
        if not self._query:
            raise GmailReadonlyError("gmail_query_required")
        if batch_size <= 0 or batch_size > 500:
            raise GmailReadonlyError("gmail_batch_size_invalid")
        if max_pages <= 0 or max_pages > 100:
            raise GmailReadonlyError("gmail_max_pages_invalid")
        self._batch_size = batch_size
        self._max_pages = max_pages

    def list_message_ids(self) -> tuple[str, ...]:
        page_token = None
        found: list[str] = []
        seen: set[str] = set()
        for _ in range(self._max_pages):
            message_ids, next_token = self._transport.list_messages(
                query=self._query,
                page_token=page_token,
                max_results=min(self._batch_size - len(found), 500),
            )
            for message_id in message_ids:
                normalized = _bounded_text(message_id, "gmail_message_id", 256)
                if normalized not in seen:
                    seen.add(normalized)
                    found.append(normalized)
                if len(found) >= self._batch_size:
                    return tuple(found)
            if not next_token:
                break
            page_token = _bounded_text(next_token, "gmail_page_token", 2048)
        return tuple(found)

    def attachment_candidates(
        self, message_id: str
    ) -> tuple[GmailAttachmentCandidate, ...]:
        message_id = _bounded_text(message_id, "gmail_message_id", 256)
        payload = self._transport.get_message(message_id)
        if not isinstance(payload, dict):
            raise GmailReadonlyError("gmail_message_invalid")
        message_payload = payload.get("payload")
        if not isinstance(message_payload, dict):
            return ()
        headers = _headers(message_payload.get("headers"))
        thread_id = _optional_bounded(payload.get("threadId"), 256)
        internal_date = _optional_bounded(payload.get("internalDate"), 64)
        candidates: list[GmailAttachmentCandidate] = []
        for part in _walk_parts(message_payload):
            filename = _optional_bounded(part.get("filename"), MAX_FILENAME_LENGTH)
            if not filename:
                continue
            body = part.get("body")
            if not isinstance(body, dict):
                continue
            part_id = _optional_bounded(part.get("partId"), 256) or "root"
            attachment_id = _optional_bounded(body.get("attachmentId"), 1024)
            inline_data = _optional_bounded(
                body.get("data"), MAX_INLINE_ENCODED_BYTES
            )
            if not attachment_id and not inline_data:
                continue
            source_key = attachment_id or f"inline:{part_id}"
            raw_size = body.get("size")
            declared_size = None
            if raw_size is not None:
                try:
                    declared_size = int(raw_size)
                except (TypeError, ValueError):
                    raise GmailReadonlyError("gmail_attachment_size_invalid") from None
                if declared_size < 0:
                    raise GmailReadonlyError("gmail_attachment_size_invalid")
            candidates.append(
                GmailAttachmentCandidate(
                    message_id=message_id,
                    thread_id=thread_id,
                    source_attachment_key=source_key,
                    gmail_attachment_id=attachment_id,
                    mime_part_id=part_id,
                    filename=filename,
                    mime_type=_optional_bounded(part.get("mimeType"), 255)
                    or "application/octet-stream",
                    declared_size=declared_size,
                    sender=headers.get("from"),
                    subject=headers.get("subject"),
                    internal_date=internal_date,
                    _inline_data=inline_data,
                )
            )
        return tuple(candidates)

    def download(self, candidate: GmailAttachmentCandidate, *, maximum: int) -> bytes:
        if maximum <= 0:
            raise GmailReadonlyError("gmail_attachment_limit_invalid")
        if candidate.declared_size is not None and candidate.declared_size > maximum:
            raise GmailReadonlyError("gmail_attachment_too_large")
        encoded = candidate._inline_data
        if candidate.gmail_attachment_id is not None:
            encoded = self._transport.get_attachment(
                candidate.message_id, candidate.gmail_attachment_id
            )
        if not encoded:
            raise GmailReadonlyError("gmail_attachment_empty")
        estimated_size = (len(encoded) * 3) // 4
        if estimated_size > maximum + 3:
            raise GmailReadonlyError("gmail_attachment_too_large")
        try:
            padded = encoded + "=" * (-len(encoded) % 4)
            decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        except Exception:
            raise GmailReadonlyError("gmail_attachment_encoding_invalid") from None
        if not decoded:
            raise GmailReadonlyError("gmail_attachment_empty")
        if len(decoded) > maximum:
            raise GmailReadonlyError("gmail_attachment_too_large")
        return decoded


def _walk_parts(root: dict[str, object]) -> Iterable[dict[str, object]]:
    pending = [root]
    visited = 0
    while pending:
        current = pending.pop()
        visited += 1
        if visited > MAX_MIME_PARTS:
            raise GmailReadonlyError("gmail_mime_tree_too_large")
        yield current
        children = current.get("parts")
        if children is None:
            continue
        if not isinstance(children, list):
            raise GmailReadonlyError("gmail_mime_tree_invalid")
        for child in reversed(children):
            if isinstance(child, dict):
                pending.append(child)


def _headers(value: object) -> dict[str, str]:
    result: dict[str, str] = {}
    if not isinstance(value, list):
        return result
    for item in value[:100]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip().lower()
        if name not in {"from", "subject"} or name in result:
            continue
        text = _optional_bounded(item.get("value"), 998)
        if text is not None:
            result[name] = text
    return result


def _bounded_text(value: object, field: str, maximum: int) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or len(text) > maximum or any(c in text for c in "\r\n\x00"):
        raise GmailReadonlyError(f"{field}_invalid")
    return text


def _optional_bounded(value: object, maximum: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > maximum or any(c in text for c in "\r\n\x00"):
        raise GmailReadonlyError("gmail_metadata_invalid")
    return text
