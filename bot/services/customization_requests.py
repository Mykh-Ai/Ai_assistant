from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from bot.services.db import managed_connection


STATUS_CONFIRMED_PENDING_REVIEW = 'confirmed_pending_review'
STATUS_REVIEWED_ACCEPTED = 'reviewed_accepted'
STATUS_REVIEWED_REJECTED = 'reviewed_rejected'
STATUS_NEEDS_USER_INPUT = 'needs_user_input'
STATUS_CONVERTED_TO_PRODUCT_TRUTH_CANDIDATE = 'converted_to_product_truth_candidate'
STATUS_CONVERTED_TO_BACKLOG = 'converted_to_backlog'
STATUS_CANCELLED_BY_USER = 'cancelled_by_user'
STATUS_EXPIRED_UNCONFIRMED = 'expired_unconfirmed'
STATUS_DRAFT_UNCONFIRMED = 'draft_unconfirmed'

ALLOWED_PERSISTED_STATUSES = {
    STATUS_CONFIRMED_PENDING_REVIEW,
    STATUS_REVIEWED_ACCEPTED,
    STATUS_REVIEWED_REJECTED,
    STATUS_NEEDS_USER_INPUT,
    STATUS_CONVERTED_TO_PRODUCT_TRUTH_CANDIDATE,
    STATUS_CONVERTED_TO_BACKLOG,
    STATUS_CANCELLED_BY_USER,
    STATUS_EXPIRED_UNCONFIRMED,
}

_VALID_SOURCE_CHANNELS = {'text', 'voice'}
_DEFAULT_RISK_LEVEL = 'medium'
_DEFAULT_SCHEMA_VERSION = 1
_SECRET_MARKER = '[REDACTED]'


@dataclass(frozen=True)
class CustomizationRequestRecord:
    request_id: str
    telegram_id: int
    supplier_telegram_id: int | None
    workspace_id: str | None
    source_channel: str
    source_triage_class: str
    source_capability_id: str | None
    source_topic_id: str | None
    normalized_title: str
    normalized_summary: str
    redacted_original_text: str | None
    raw_text_hash: str | None
    language_hint: str | None
    confidence: float | None
    status: str
    risk_level: str | None
    requires_human_approval: bool
    product_truth_relation: str | None
    privacy_redaction_flags: str | None
    admin_note: str | None
    reviewed_by: int | None
    created_at: str
    updated_at: str
    confirmed_at: str | None
    reviewed_at: str | None
    schema_version: int


class CustomizationRequestService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def create_confirmed_customization_request(
        self,
        *,
        telegram_id: int | None,
        source_channel: str,
        source_triage_class: str,
        normalized_title: str,
        normalized_summary: str,
        request_id: str | None = None,
        supplier_telegram_id: int | None = None,
        workspace_id: str | None = None,
        source_capability_id: str | None = None,
        source_topic_id: str | None = None,
        original_user_text: str | None = None,
        redacted_original_text: str | None = None,
        raw_text_hash: str | None = None,
        language_hint: str | None = None,
        confidence: float | int | str | None = None,
        status: str = STATUS_CONFIRMED_PENDING_REVIEW,
        risk_level: str | None = None,
        product_truth_relation: str | None = None,
        privacy_redaction_flags: str | None = None,
    ) -> CustomizationRequestRecord:
        if telegram_id is None:
            raise ValueError('telegram_id_required')
        if int(telegram_id) <= 0:
            raise ValueError('telegram_id_required')

        clean_title = _required_text(normalized_title, 'normalized_title_required')
        clean_summary = _required_text(normalized_summary, 'normalized_summary_required')
        clean_channel = _required_text(source_channel, 'source_channel_required')
        if clean_channel not in _VALID_SOURCE_CHANNELS:
            raise ValueError('invalid_source_channel')

        clean_triage_class = _required_text(source_triage_class, 'source_triage_class_required')
        clean_status = _normalize_status(status)
        clean_request_id = _clean_optional(request_id) or f'cr_{uuid4().hex}'
        now = _utc_timestamp()
        clean_original = _clean_optional(redacted_original_text)
        raw_source = _clean_optional(original_user_text)
        if clean_original is None and raw_source is not None:
            clean_original = redact_customization_request_text(raw_source)

        clean_hash = _clean_optional(raw_text_hash)
        if clean_hash is None and raw_source is not None:
            clean_hash = hash_raw_text(raw_source)

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            try:
                connection.execute(
                    (
                        'INSERT INTO customization_requests '
                        '(request_id, telegram_id, supplier_telegram_id, workspace_id, source_channel, '
                        'source_triage_class, source_capability_id, source_topic_id, normalized_title, '
                        'normalized_summary, redacted_original_text, raw_text_hash, language_hint, confidence, '
                        'status, risk_level, requires_human_approval, product_truth_relation, '
                        'privacy_redaction_flags, admin_note, reviewed_by, created_at, updated_at, '
                        'confirmed_at, reviewed_at, schema_version) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, '
                        'NULL, NULL, ?, ?, ?, NULL, ?)'
                    ),
                    (
                        clean_request_id,
                        int(telegram_id),
                        supplier_telegram_id,
                        _clean_optional(workspace_id),
                        clean_channel,
                        clean_triage_class,
                        _clean_optional(source_capability_id),
                        _clean_optional(source_topic_id),
                        clean_title,
                        clean_summary,
                        clean_original,
                        clean_hash,
                        _clean_optional(language_hint),
                        _normalize_confidence(confidence),
                        clean_status,
                        _clean_optional(risk_level) or _DEFAULT_RISK_LEVEL,
                        _clean_optional(product_truth_relation),
                        _clean_optional(privacy_redaction_flags),
                        now,
                        now,
                        now,
                        _DEFAULT_SCHEMA_VERSION,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                if 'UNIQUE' in str(exc).upper() or 'PRIMARY' in str(exc).upper():
                    raise ValueError('request_id_already_exists') from exc
                raise

            row = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError('customization_request_save_failed')
        return _record_from_row(row)

    def get_customization_request_by_id(
        self,
        *,
        request_id: str,
        telegram_id: int | None = None,
    ) -> CustomizationRequestRecord | None:
        clean_request_id = _clean_optional(request_id)
        if clean_request_id is None:
            return None

        params: list[object] = [clean_request_id]
        where_clause = ' WHERE request_id = ?'
        if telegram_id is not None:
            where_clause += ' AND telegram_id = ?'
            params.append(int(telegram_id))

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(_SELECT_CUSTOMIZATION_REQUEST + where_clause, params).fetchone()
        return _record_from_row(row) if row is not None else None

    def list_customization_requests_for_user(
        self,
        *,
        telegram_id: int,
        status: str | None = None,
    ) -> list[CustomizationRequestRecord]:
        params: list[object] = [int(telegram_id)]
        where_clause = ' WHERE telegram_id = ?'
        if status is not None:
            where_clause += ' AND status = ?'
            params.append(_normalize_status(status))

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + where_clause + ' ORDER BY created_at DESC, request_id DESC',
                params,
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def list_pending_customization_requests(self) -> list[CustomizationRequestRecord]:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    _SELECT_CUSTOMIZATION_REQUEST
                    + ' WHERE status = ? ORDER BY created_at ASC, request_id ASC'
                ),
                (STATUS_CONFIRMED_PENDING_REVIEW,),
            ).fetchall()
        return [_record_from_row(row) for row in rows]


def redact_customization_request_text(value: str | None) -> str | None:
    text = _clean_optional(value)
    if text is None:
        return None

    redacted = text
    redacted = re.sub(r'\bsk-[A-Za-z0-9_-]{8,}\b', _SECRET_MARKER, redacted)
    redacted = re.sub(
        r'(?i)\b(password|passwd|heslo|secret|token|api[_ -]?key)\b\s*[:=]?\s*\S+',
        lambda match: f"{match.group(1)}: {_SECRET_MARKER}",
        redacted,
    )
    redacted = re.sub(
        r'\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b',
        _SECRET_MARKER,
        redacted,
    )
    redacted = re.sub(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        _SECRET_MARKER,
        redacted,
    )
    redacted = re.sub(
        r'(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9])',
        _SECRET_MARKER,
        redacted,
    )
    return redacted


def hash_raw_text(value: str | None) -> str | None:
    text = _clean_optional(value)
    if text is None:
        return None
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _normalize_confidence(value: float | int | str | None) -> float | None:
    if value is None:
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, confidence))


def _normalize_status(value: str) -> str:
    status = _required_text(value, 'status_required')
    if status == STATUS_DRAFT_UNCONFIRMED:
        raise ValueError('draft_unconfirmed_not_persisted')
    if status not in ALLOWED_PERSISTED_STATUSES:
        raise ValueError('invalid_customization_request_status')
    return status


def _required_text(value: str | None, error: str) -> str:
    text = _clean_optional(value)
    if text is None:
        raise ValueError(error)
    return text


def _clean_optional(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


_SELECT_CUSTOMIZATION_REQUEST = (
    'SELECT request_id, telegram_id, supplier_telegram_id, workspace_id, source_channel, '
    'source_triage_class, source_capability_id, source_topic_id, normalized_title, '
    'normalized_summary, redacted_original_text, raw_text_hash, language_hint, confidence, '
    'status, risk_level, requires_human_approval, product_truth_relation, privacy_redaction_flags, '
    'admin_note, reviewed_by, created_at, updated_at, confirmed_at, reviewed_at, schema_version '
    'FROM customization_requests'
)


def _record_from_row(row: sqlite3.Row) -> CustomizationRequestRecord:
    return CustomizationRequestRecord(
        request_id=row['request_id'],
        telegram_id=int(row['telegram_id']),
        supplier_telegram_id=row['supplier_telegram_id'],
        workspace_id=row['workspace_id'],
        source_channel=row['source_channel'],
        source_triage_class=row['source_triage_class'],
        source_capability_id=row['source_capability_id'],
        source_topic_id=row['source_topic_id'],
        normalized_title=row['normalized_title'],
        normalized_summary=row['normalized_summary'],
        redacted_original_text=row['redacted_original_text'],
        raw_text_hash=row['raw_text_hash'],
        language_hint=row['language_hint'],
        confidence=row['confidence'],
        status=row['status'],
        risk_level=row['risk_level'],
        requires_human_approval=bool(row['requires_human_approval']),
        product_truth_relation=row['product_truth_relation'],
        privacy_redaction_flags=row['privacy_redaction_flags'],
        admin_note=row['admin_note'],
        reviewed_by=row['reviewed_by'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        confirmed_at=row['confirmed_at'],
        reviewed_at=row['reviewed_at'],
        schema_version=int(row['schema_version']),
    )
