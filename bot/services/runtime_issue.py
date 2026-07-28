from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3

from bot.services.db import (
    RUNTIME_ISSUE_SCHEMA_VERSION,
    managed_connection,
    validate_runtime_issue_schema,
)


RUNTIME_ISSUE_INTAKE_STATUS = 'new'
RUNTIME_ISSUE_RECORD_VERSION = 1
RUNTIME_ISSUE_REDACTION_POLICY = 'runtime-issue-redaction-v1'
RUNTIME_ISSUE_FSM_CONTEXT_SCHEMA = 'runtime-issue-fsm-context-v1'
RUNTIME_ISSUE_DEDUPLICATION_VERSION = 'runtime-issue-delivery-v1'

_DESCRIPTION_MIN_LENGTH = 10
_DESCRIPTION_MAX_LENGTH = 2000
_TITLE_MAX_LENGTH = 120
_FSM_STATE_MAX_LENGTH = 200
_HEX_SHA_PATTERN = re.compile(r'^[0-9a-fA-F]{40}$')
_SAFE_FSM_CONTEXT_KEYS = {
    'invoice_draft': 'invoice_draft_present',
    'invoice_partial_draft': 'invoice_partial_draft_present',
    'contact_draft': 'contact_draft_present',
    'accounting_document_candidate': 'accounting_document_candidate_present',
    'work_time_entry_draft': 'work_time_entry_draft_present',
    'customization_request_draft': 'customization_request_draft_present',
}

_PRIVATE_KEY_BLOCK = re.compile(
    r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----',
    flags=re.DOTALL,
)
_PRIVATE_KEY_MARKER = re.compile(r'-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----')
_AUTHORIZATION_HEADER = re.compile(
    r'(?i)\bauthorization\s*:\s*(?:bearer\s+)?[^\s,;]+'
)
_SECRET_ASSIGNMENT = re.compile(
    (
        r'(?i)\b(password|passwd|pwd|token|api[_-]?key|secret|client[_-]?secret|'
        r"""connection[_-]?string)\s*[:=]\s*("[^"\r\n]*"|'[^'\r\n]*'|[^\s,;]+)"""
    )
)
_CREDENTIAL_URL = re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@')
_WINDOWS_PRIVATE_PATH = re.compile(r'(?<!\w)[A-Za-z]:\\[^\s,;]+')
_UNIX_PRIVATE_PATH = re.compile(r'(?<!\w)/(?:root|home|etc|var|opt|srv|mnt)/[^\s,;]+')
_ENV_ASSIGNMENT_LINE = re.compile(r'(?m)^[A-Z][A-Z0-9_]{2,}\s*=\s*.+$')


class RuntimeIssueError(RuntimeError):
    pass


class RuntimeIssueUnsafeInput(RuntimeIssueError):
    pass


class RuntimeIssueInvalidInput(RuntimeIssueError):
    pass


@dataclass(frozen=True)
class RuntimeIssueCaptureInput:
    description: str
    actor_telegram_id: int
    telegram_update_id: int
    telegram_message_id: int
    telegram_chat_id: int
    workspace_id: str | None
    workspace_resolution_reason: str
    source_channel: str
    active_fsm_state: str | None
    active_fsm_data: Mapping[str, object]
    reported_build_sha: str | None
    build_sha_status: str


@dataclass(frozen=True)
class RuntimeIssueRecord:
    issue_id: str
    schema_version: int
    intake_status: str
    description: str
    short_title: str
    reported_at: str
    actor_telegram_id: int
    telegram_update_id: int
    telegram_message_id: int
    telegram_chat_id: int
    workspace_id: str | None
    workspace_resolution_reason: str
    source_channel: str
    active_fsm_state: str | None
    active_fsm_context_summary: dict[str, object]
    reported_build_sha: str | None
    build_sha_status: str
    privacy_metadata: dict[str, object]
    deduplication_key: str
    record_version: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RuntimeIssueCaptureResult:
    record: RuntimeIssueRecord
    duplicate: bool


@dataclass(frozen=True)
class SanitizedRuntimeIssue:
    description: str
    short_title: str
    fsm_context_summary: dict[str, object]
    privacy_metadata: dict[str, object]


def sanitize_runtime_issue(
    *,
    description: str,
    active_fsm_data: Mapping[str, object],
) -> SanitizedRuntimeIssue:
    if not isinstance(description, str):
        raise RuntimeIssueInvalidInput('runtime_issue_description_required')
    if '\x00' in description or any(
        ord(character) < 32 and character not in {'\n', '\r', '\t'}
        for character in description
    ):
        raise RuntimeIssueUnsafeInput('runtime_issue_unsafe_control_character')
    if _PRIVATE_KEY_MARKER.search(description) and not _PRIVATE_KEY_BLOCK.search(description):
        raise RuntimeIssueUnsafeInput('runtime_issue_incomplete_private_key')
    if len(_ENV_ASSIGNMENT_LINE.findall(description)) >= 3:
        raise RuntimeIssueUnsafeInput('runtime_issue_environment_dump_rejected')

    redaction_categories: set[str] = set()
    sanitized = description

    def _replace(
        pattern: re.Pattern[str],
        replacement: str | Callable[[re.Match[str]], str],
        category: str,
    ) -> None:
        nonlocal sanitized
        sanitized, count = pattern.subn(replacement, sanitized)
        if count:
            redaction_categories.add(category)

    _replace(_PRIVATE_KEY_BLOCK, '[REDACTED PRIVATE KEY]', 'private_key')
    _replace(_AUTHORIZATION_HEADER, 'Authorization: [REDACTED]', 'authorization_header')
    _replace(
        _SECRET_ASSIGNMENT,
        lambda match: f'{match.group(1)}=[REDACTED]',
        'secret_assignment',
    )
    _replace(_CREDENTIAL_URL, r'\1[REDACTED]@', 'connection_credentials')
    _replace(_WINDOWS_PRIVATE_PATH, '[REDACTED PATH]', 'private_path')
    _replace(_UNIX_PRIVATE_PATH, '[REDACTED PATH]', 'private_path')

    sanitized = re.sub(r'[ \t]+', ' ', sanitized)
    sanitized = re.sub(r'\s*\n\s*', '\n', sanitized).strip()
    description_truncated = len(sanitized) > _DESCRIPTION_MAX_LENGTH
    if description_truncated:
        sanitized = sanitized[:_DESCRIPTION_MAX_LENGTH].rstrip()
    if len(sanitized) < _DESCRIPTION_MIN_LENGTH:
        raise RuntimeIssueInvalidInput('runtime_issue_description_length')

    title_source = next(
        (line.strip() for line in sanitized.splitlines() if line.strip()),
        sanitized,
    )
    short_title = title_source[:_TITLE_MAX_LENGTH].rstrip()
    if not short_title:
        raise RuntimeIssueInvalidInput('runtime_issue_title_empty')

    summarized_keys = sorted(
        safe_label
        for key, safe_label in _SAFE_FSM_CONTEXT_KEYS.items()
        if key in active_fsm_data
    )
    fsm_context_summary: dict[str, object] = {
        'schema_version': RUNTIME_ISSUE_FSM_CONTEXT_SCHEMA,
        'present_contexts': summarized_keys,
    }
    privacy_metadata: dict[str, object] = {
        'redaction_policy': RUNTIME_ISSUE_REDACTION_POLICY,
        'redaction_categories': sorted(redaction_categories),
        'description_truncated': description_truncated,
        'fsm_context_allowlisted': True,
        'fsm_context_keys_summarized': len(summarized_keys),
        'fsm_context_keys_ignored': max(0, len(active_fsm_data) - len(summarized_keys)),
    }
    return SanitizedRuntimeIssue(
        description=sanitized,
        short_title=short_title,
        fsm_context_summary=fsm_context_summary,
        privacy_metadata=privacy_metadata,
    )


class RuntimeIssueService:
    _SELECT_COLUMNS = (
        'issue_id, schema_version, intake_status, description, short_title, '
        'reported_at, actor_telegram_id, telegram_update_id, telegram_message_id, '
        'telegram_chat_id, workspace_id, workspace_resolution_reason, source_channel, '
        'active_fsm_state, active_fsm_context_summary_json, reported_build_sha, '
        'build_sha_status, privacy_metadata_json, deduplication_key, record_version, '
        'created_at, updated_at'
    )

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def capture(self, payload: RuntimeIssueCaptureInput) -> RuntimeIssueCaptureResult:
        self._validate_trusted_payload(payload)
        sanitized = sanitize_runtime_issue(
            description=payload.description,
            active_fsm_data=payload.active_fsm_data,
        )
        now = datetime.now(UTC)
        reported_at = now.isoformat()
        deduplication_key = self._deduplication_key(payload)
        candidate_issue_id = self._issue_id(now)
        fsm_state = self._bounded_fsm_state(payload.active_fsm_state)
        fsm_context_json = self._json(sanitized.fsm_context_summary)
        privacy_metadata_json = self._json(sanitized.privacy_metadata)

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            validate_runtime_issue_schema(connection)
            try:
                connection.execute('BEGIN IMMEDIATE')
                cursor = connection.execute(
                    (
                        'INSERT INTO runtime_issues ('
                        'issue_id, schema_version, intake_status, description, short_title, '
                        'reported_at, actor_telegram_id, telegram_update_id, '
                        'telegram_message_id, telegram_chat_id, workspace_id, '
                        'workspace_resolution_reason, source_channel, active_fsm_state, '
                        'active_fsm_context_summary_json, reported_build_sha, '
                        'build_sha_status, privacy_metadata_json, deduplication_key, '
                        'record_version, created_at, updated_at'
                        ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) '
                        'ON CONFLICT(deduplication_key) DO NOTHING'
                    ),
                    (
                        candidate_issue_id,
                        RUNTIME_ISSUE_SCHEMA_VERSION,
                        RUNTIME_ISSUE_INTAKE_STATUS,
                        sanitized.description,
                        sanitized.short_title,
                        reported_at,
                        payload.actor_telegram_id,
                        payload.telegram_update_id,
                        payload.telegram_message_id,
                        payload.telegram_chat_id,
                        payload.workspace_id,
                        payload.workspace_resolution_reason,
                        payload.source_channel,
                        fsm_state,
                        fsm_context_json,
                        payload.reported_build_sha,
                        payload.build_sha_status,
                        privacy_metadata_json,
                        deduplication_key,
                        RUNTIME_ISSUE_RECORD_VERSION,
                        reported_at,
                        reported_at,
                    ),
                )
                inserted = cursor.rowcount == 1
                row = connection.execute(
                    (
                        f'SELECT {self._SELECT_COLUMNS} FROM runtime_issues '
                        'WHERE deduplication_key = ? AND actor_telegram_id = ? '
                        'AND telegram_chat_id = ? AND source_channel = ?'
                    ),
                    (
                        deduplication_key,
                        payload.actor_telegram_id,
                        payload.telegram_chat_id,
                        payload.source_channel,
                    ),
                ).fetchone()
                if row is None:
                    raise RuntimeIssueError('runtime_issue_insert_not_readable')
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return RuntimeIssueCaptureResult(
            record=self._record_from_row(row),
            duplicate=not inserted,
        )

    def get_for_actor(
        self,
        *,
        issue_id: str,
        actor_telegram_id: int,
        workspace_id: str | None,
    ) -> RuntimeIssueRecord | None:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            validate_runtime_issue_schema(connection)
            row = connection.execute(
                (
                    f'SELECT {self._SELECT_COLUMNS} FROM runtime_issues '
                    'WHERE issue_id = ? AND actor_telegram_id = ? AND workspace_id IS ?'
                ),
                (issue_id, actor_telegram_id, workspace_id),
            ).fetchone()
        return self._record_from_row(row) if row is not None else None

    @staticmethod
    def _validate_trusted_payload(payload: RuntimeIssueCaptureInput) -> None:
        for field_name in (
            'actor_telegram_id',
            'telegram_update_id',
            'telegram_message_id',
            'telegram_chat_id',
        ):
            value = getattr(payload, field_name)
            if not isinstance(value, int):
                raise RuntimeIssueInvalidInput(f'runtime_issue_trusted_{field_name}_required')
        if payload.workspace_resolution_reason not in {
            'active_workspace',
            'no_active_workspace',
        }:
            raise RuntimeIssueInvalidInput('runtime_issue_workspace_reason')
        if payload.workspace_resolution_reason == 'active_workspace' and not payload.workspace_id:
            raise RuntimeIssueInvalidInput('runtime_issue_workspace_required')
        if payload.workspace_resolution_reason == 'no_active_workspace' and payload.workspace_id is not None:
            raise RuntimeIssueInvalidInput('runtime_issue_workspace_must_be_null')
        if payload.source_channel not in {'text', 'voice'}:
            raise RuntimeIssueInvalidInput('runtime_issue_source_channel')
        if payload.build_sha_status not in {'known', 'unavailable', 'stale'}:
            raise RuntimeIssueInvalidInput('runtime_issue_build_sha_status')
        if payload.reported_build_sha is not None and not _HEX_SHA_PATTERN.fullmatch(
            payload.reported_build_sha
        ):
            raise RuntimeIssueInvalidInput('runtime_issue_build_sha')
        if payload.build_sha_status == 'known' and payload.reported_build_sha is None:
            raise RuntimeIssueInvalidInput('runtime_issue_known_build_sha_required')

    @staticmethod
    def _bounded_fsm_state(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized[:_FSM_STATE_MAX_LENGTH]

    @staticmethod
    def _deduplication_key(payload: RuntimeIssueCaptureInput) -> str:
        identity = (
            f'{RUNTIME_ISSUE_DEDUPLICATION_VERSION}|{payload.actor_telegram_id}|'
            f'{payload.telegram_chat_id}|{payload.telegram_update_id}|'
            f'{payload.telegram_message_id}|{payload.source_channel}'
        )
        return hashlib.sha256(identity.encode('utf-8')).hexdigest()

    @staticmethod
    def _issue_id(now: datetime) -> str:
        return f'IR-{now.astimezone(UTC):%Y%m%d}-{secrets.token_hex(6).upper()}'

    @staticmethod
    def _json(value: Mapping[str, object]) -> str:
        return json.dumps(
            dict(value),
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True,
        )

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> RuntimeIssueRecord:
        return RuntimeIssueRecord(
            issue_id=str(row['issue_id']),
            schema_version=int(row['schema_version']),
            intake_status=str(row['intake_status']),
            description=str(row['description']),
            short_title=str(row['short_title']),
            reported_at=str(row['reported_at']),
            actor_telegram_id=int(row['actor_telegram_id']),
            telegram_update_id=int(row['telegram_update_id']),
            telegram_message_id=int(row['telegram_message_id']),
            telegram_chat_id=int(row['telegram_chat_id']),
            workspace_id=(
                str(row['workspace_id']) if row['workspace_id'] is not None else None
            ),
            workspace_resolution_reason=str(row['workspace_resolution_reason']),
            source_channel=str(row['source_channel']),
            active_fsm_state=(
                str(row['active_fsm_state'])
                if row['active_fsm_state'] is not None
                else None
            ),
            active_fsm_context_summary=json.loads(
                str(row['active_fsm_context_summary_json'])
            ),
            reported_build_sha=(
                str(row['reported_build_sha'])
                if row['reported_build_sha'] is not None
                else None
            ),
            build_sha_status=str(row['build_sha_status']),
            privacy_metadata=json.loads(str(row['privacy_metadata_json'])),
            deduplication_key=str(row['deduplication_key']),
            record_version=int(row['record_version']),
            created_at=str(row['created_at']),
            updated_at=str(row['updated_at']),
        )
