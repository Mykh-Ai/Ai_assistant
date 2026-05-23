from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
REVIEW_RESULT_UPDATED = 'updated'
REVIEW_RESULT_NOT_FOUND = 'not_found'
REVIEW_RESULT_ALREADY_PROCESSED = 'already_processed'
RESPONSE_KIND_ANSWER = 'answer'
RESPONSE_DELIVERY_PENDING = 'send_pending'
RESPONSE_DELIVERY_SUCCEEDED = 'send_succeeded'
RESPONSE_DELIVERY_FAILED = 'send_failed'
RESPONSE_RESULT_PREPARED = 'prepared'
RESPONSE_RESULT_NOT_FOUND = 'not_found'
RESPONSE_RESULT_ALREADY_SENT = 'already_sent'

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

REQUEST_STARTING_TRIAGE_CLASSES = {
    'new_business_feature_request',
    'customization_request_candidate',
    'admin_review_candidate',
    'possible_product_truth_candidate',
}

_VALID_SOURCE_CHANNELS = {'text', 'voice'}
_VALID_RESPONSE_KINDS = {RESPONSE_KIND_ANSWER}
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
    admin_response_text: str | None
    response_kind: str | None
    response_sent_at: str | None
    response_sent_by: int | None
    response_delivery_status: str | None
    response_attempts: int
    response_failed_reason: str | None
    responded_to_request_status: str | None
    response_updated_at: str | None
    response_id: str | None
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

        clean_triage_class = _normalize_source_triage_class(source_triage_class)
        clean_status = _normalize_status(status)
        clean_request_id = _clean_optional(request_id) or f'cr_{uuid4().hex}'
        now = _utc_timestamp()
        clean_original = redact_customization_request_text(redacted_original_text)
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

    def get_customization_request_for_user(
        self,
        *,
        request_id: str,
        telegram_id: int | None,
    ) -> CustomizationRequestRecord | None:
        if telegram_id is None:
            raise ValueError('telegram_id_required')
        if int(telegram_id) <= 0:
            raise ValueError('telegram_id_required')

        clean_request_id = _clean_optional(request_id)
        if clean_request_id is None:
            return None

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ? AND telegram_id = ?',
                (clean_request_id, int(telegram_id)),
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    def get_customization_request_by_id_for_admin(
        self,
        *,
        request_id: str,
    ) -> CustomizationRequestRecord | None:
        """Admin/internal unscoped lookup; user-facing reads must use tenant scope."""
        clean_request_id = _clean_optional(request_id)
        if clean_request_id is None:
            return None

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    def find_customization_requests_by_id_prefix_for_admin(
        self,
        *,
        request_id_prefix: str,
        limit: int | None = None,
    ) -> list[CustomizationRequestRecord]:
        """Admin/internal unscoped prefix lookup; user-facing reads must use tenant scope."""
        clean_prefix = _clean_optional(request_id_prefix)
        if clean_prefix is None:
            return []

        clean_limit = _normalize_limit(limit)
        query = _SELECT_CUSTOMIZATION_REQUEST + ' WHERE substr(request_id, 1, ?) = ? ORDER BY created_at DESC, request_id DESC'
        params: list[object] = [len(clean_prefix), clean_prefix]
        if clean_limit is not None:
            query += ' LIMIT ?'
            params.append(clean_limit)

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(query, params).fetchall()
        return [_record_from_row(row) for row in rows]

    def mark_customization_request_reviewed_for_admin(
        self,
        *,
        request_id: str,
        admin_telegram_id: int | None,
        decision: str,
    ) -> tuple[str, CustomizationRequestRecord | None]:
        """Admin/internal status-only review transition; does not create downstream work."""
        if admin_telegram_id is None or int(admin_telegram_id) <= 0:
            raise ValueError('admin_telegram_id_required')

        clean_request_id = _clean_optional(request_id)
        if clean_request_id is None:
            return REVIEW_RESULT_NOT_FOUND, None

        clean_decision = _normalize_status(decision)
        if clean_decision not in {STATUS_REVIEWED_ACCEPTED, STATUS_REVIEWED_REJECTED}:
            raise ValueError('invalid_review_decision')

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()
            if existing is None:
                return REVIEW_RESULT_NOT_FOUND, None
            if existing['status'] != STATUS_CONFIRMED_PENDING_REVIEW:
                return REVIEW_RESULT_ALREADY_PROCESSED, _record_from_row(existing)

            now = _utc_timestamp_after(existing['updated_at'])
            cursor = connection.execute(
                (
                    'UPDATE customization_requests '
                    'SET status = ?, reviewed_by = ?, reviewed_at = ?, updated_at = ? '
                    'WHERE request_id = ? AND status = ?'
                ),
                (
                    clean_decision,
                    int(admin_telegram_id),
                    now,
                    now,
                    clean_request_id,
                    STATUS_CONFIRMED_PENDING_REVIEW,
                ),
            )
            if cursor.rowcount == 0:
                connection.commit()
                current = connection.execute(
                    _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                    (clean_request_id,),
                ).fetchone()
                if current is None:
                    return REVIEW_RESULT_NOT_FOUND, None
                return REVIEW_RESULT_ALREADY_PROCESSED, _record_from_row(current)

            connection.commit()
            row = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()

        if row is None:
            return REVIEW_RESULT_NOT_FOUND, None
        return REVIEW_RESULT_UPDATED, _record_from_row(row)

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

    def list_pending_customization_requests_for_admin(self, *, limit: int | None = None) -> list[CustomizationRequestRecord]:
        """Admin/internal pending-review primitive; not a tenant-user listing API."""
        clean_limit = _normalize_limit(limit)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            query = _SELECT_CUSTOMIZATION_REQUEST + ' WHERE status = ? ORDER BY created_at DESC, request_id DESC'
            params: list[object] = [STATUS_CONFIRMED_PENDING_REVIEW]
            if clean_limit is not None:
                query += ' LIMIT ?'
                params.append(clean_limit)
            rows = connection.execute(query, params).fetchall()
        return [_record_from_row(row) for row in rows]

    def persist_customization_request_response_attempt(
        self,
        *,
        request_id: str,
        admin_telegram_id: int | None,
        response_id: str,
        response_text: str,
        response_kind: str = RESPONSE_KIND_ANSWER,
    ) -> tuple[str, CustomizationRequestRecord | None]:
        """Persist latest confirmed response before outbound Telegram delivery."""
        if admin_telegram_id is None or int(admin_telegram_id) <= 0:
            raise ValueError('admin_telegram_id_required')

        clean_request_id = _clean_optional(request_id)
        clean_response_id = _required_text(response_id, 'response_id_required')
        clean_response_kind = _normalize_response_kind(response_kind)
        clean_response_text = redact_customization_request_text(response_text)
        if clean_response_text is None:
            raise ValueError('admin_response_text_required')

        if clean_request_id is None:
            return RESPONSE_RESULT_NOT_FOUND, None

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()
            if existing is None:
                return RESPONSE_RESULT_NOT_FOUND, None
            if (
                existing['response_id'] == clean_response_id
                and existing['response_delivery_status'] == RESPONSE_DELIVERY_SUCCEEDED
            ):
                return RESPONSE_RESULT_ALREADY_SENT, _record_from_row(existing)

            now = _utc_timestamp_after(existing['updated_at'])
            connection.execute(
                (
                    'UPDATE customization_requests '
                    'SET admin_response_text = ?, response_kind = ?, response_sent_by = ?, '
                    'response_delivery_status = ?, response_attempts = COALESCE(response_attempts, 0) + 1, '
                    'response_failed_reason = NULL, responded_to_request_status = ?, response_updated_at = ?, '
                    'response_id = ?, updated_at = ? '
                    'WHERE request_id = ?'
                ),
                (
                    clean_response_text,
                    clean_response_kind,
                    int(admin_telegram_id),
                    RESPONSE_DELIVERY_PENDING,
                    existing['status'],
                    now,
                    clean_response_id,
                    now,
                    clean_request_id,
                ),
            )
            connection.commit()
            row = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()

        if row is None:
            return RESPONSE_RESULT_NOT_FOUND, None
        return RESPONSE_RESULT_PREPARED, _record_from_row(row)

    def mark_response_delivery_succeeded(
        self,
        *,
        request_id: str,
        response_id: str,
    ) -> tuple[str, CustomizationRequestRecord | None]:
        clean_request_id = _clean_optional(request_id)
        clean_response_id = _clean_optional(response_id)
        if clean_request_id is None or clean_response_id is None:
            return RESPONSE_RESULT_NOT_FOUND, None

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ? AND response_id = ?',
                (clean_request_id, clean_response_id),
            ).fetchone()
            if existing is None:
                return RESPONSE_RESULT_NOT_FOUND, None
            if existing['response_delivery_status'] == RESPONSE_DELIVERY_SUCCEEDED:
                return RESPONSE_RESULT_ALREADY_SENT, _record_from_row(existing)

            now = _utc_timestamp_after(existing['response_updated_at'] or existing['updated_at'])
            connection.execute(
                (
                    'UPDATE customization_requests '
                    'SET response_delivery_status = ?, response_sent_at = ?, response_failed_reason = NULL, '
                    'response_updated_at = ?, updated_at = ? '
                    'WHERE request_id = ? AND response_id = ?'
                ),
                (
                    RESPONSE_DELIVERY_SUCCEEDED,
                    now,
                    now,
                    now,
                    clean_request_id,
                    clean_response_id,
                ),
            )
            connection.commit()
            row = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()

        if row is None:
            return RESPONSE_RESULT_NOT_FOUND, None
        return RESPONSE_RESULT_PREPARED, _record_from_row(row)

    def mark_response_delivery_failed(
        self,
        *,
        request_id: str,
        response_id: str,
        failed_reason: str = 'telegram_send_failed',
    ) -> tuple[str, CustomizationRequestRecord | None]:
        clean_request_id = _clean_optional(request_id)
        clean_response_id = _clean_optional(response_id)
        if clean_request_id is None or clean_response_id is None:
            return RESPONSE_RESULT_NOT_FOUND, None

        safe_reason = _safe_failed_reason(failed_reason)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ? AND response_id = ?',
                (clean_request_id, clean_response_id),
            ).fetchone()
            if existing is None:
                return RESPONSE_RESULT_NOT_FOUND, None
            if existing['response_delivery_status'] == RESPONSE_DELIVERY_SUCCEEDED:
                return RESPONSE_RESULT_ALREADY_SENT, _record_from_row(existing)

            now = _utc_timestamp_after(existing['response_updated_at'] or existing['updated_at'])
            connection.execute(
                (
                    'UPDATE customization_requests '
                    'SET response_delivery_status = ?, response_failed_reason = ?, '
                    'response_updated_at = ?, updated_at = ? '
                    'WHERE request_id = ? AND response_id = ?'
                ),
                (
                    RESPONSE_DELIVERY_FAILED,
                    safe_reason,
                    now,
                    now,
                    clean_request_id,
                    clean_response_id,
                ),
            )
            connection.commit()
            row = connection.execute(
                _SELECT_CUSTOMIZATION_REQUEST + ' WHERE request_id = ?',
                (clean_request_id,),
            ).fetchone()

        if row is None:
            return RESPONSE_RESULT_NOT_FOUND, None
        return RESPONSE_RESULT_PREPARED, _record_from_row(row)


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


def _normalize_source_triage_class(value: str | None) -> str:
    triage_class = _required_text(value, 'source_triage_class_required')
    if triage_class not in REQUEST_STARTING_TRIAGE_CLASSES:
        raise ValueError('invalid_source_triage_class')
    return triage_class


def _normalize_status(value: str) -> str:
    status = _required_text(value, 'status_required')
    if status == STATUS_DRAFT_UNCONFIRMED:
        raise ValueError('draft_unconfirmed_not_persisted')
    if status not in ALLOWED_PERSISTED_STATUSES:
        raise ValueError('invalid_customization_request_status')
    return status


def _normalize_response_kind(value: str) -> str:
    kind = _required_text(value, 'response_kind_required')
    if kind not in _VALID_RESPONSE_KINDS:
        raise ValueError('invalid_response_kind')
    return kind


def _safe_failed_reason(value: str) -> str:
    reason = _clean_optional(value) or 'telegram_send_failed'
    if reason not in {'telegram_send_failed', 'missing_bot'}:
        return 'telegram_send_failed'
    return reason


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


def _normalize_limit(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    return max(1, min(limit, 50))


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _utc_timestamp_after(value: str | None) -> str:
    now = datetime.now(UTC).replace(microsecond=0)
    previous = _parse_utc_timestamp(value)
    if previous is not None and now <= previous:
        now = previous + timedelta(seconds=1)
    return now.isoformat().replace('+00:00', 'Z')


def _parse_utc_timestamp(value: str | None) -> datetime | None:
    text = _clean_optional(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


_SELECT_CUSTOMIZATION_REQUEST = (
    'SELECT request_id, telegram_id, supplier_telegram_id, workspace_id, source_channel, '
    'source_triage_class, source_capability_id, source_topic_id, normalized_title, '
    'normalized_summary, redacted_original_text, raw_text_hash, language_hint, confidence, '
    'status, risk_level, requires_human_approval, product_truth_relation, privacy_redaction_flags, '
    'admin_note, reviewed_by, created_at, updated_at, confirmed_at, reviewed_at, '
    'admin_response_text, response_kind, response_sent_at, response_sent_by, response_delivery_status, '
    'response_attempts, response_failed_reason, responded_to_request_status, response_updated_at, response_id, '
    'schema_version '
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
        admin_response_text=row['admin_response_text'],
        response_kind=row['response_kind'],
        response_sent_at=row['response_sent_at'],
        response_sent_by=row['response_sent_by'],
        response_delivery_status=row['response_delivery_status'],
        response_attempts=int(row['response_attempts'] or 0),
        response_failed_reason=row['response_failed_reason'],
        responded_to_request_status=row['responded_to_request_status'],
        response_updated_at=row['response_updated_at'],
        response_id=row['response_id'],
        schema_version=int(row['schema_version']),
    )
