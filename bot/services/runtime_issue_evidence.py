from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import re
import sqlite3
import subprocess

from bot.services.db import (
    managed_connection,
    validate_runtime_issue_handoff_schema,
    validate_runtime_issue_schema,
)


EVIDENCE_WINDOW = timedelta(minutes=30)
MAX_RAW_LINES = 500
MAX_RAW_BYTES = 256 * 1024
MAX_ITEMS = 20
MAX_EXCERPT = 500
EVIDENCE_CATEGORIES = ('stt', 'docker', 'network', 'provider')
_ISSUE_ID = re.compile(r'^IR-[0-9]{8}-[0-9A-F]{12}$')
_HANDOFF_ID = re.compile(r'^RH-[0-9]{8}-[0-9A-F]{12}$')
_TIMESTAMP_LINE = re.compile(r'^(\d{4}-\d\d-\d\dT[^\s]+)\s+(.*)$')
_NUMERIC_CORRELATION_FIELD = re.compile(
    r'(?<![A-Za-z0-9_])'
    r'(?P<label>'
    r'telegram_update_id|update_id|update|'
    r'telegram_message_id|message_id|message|'
    r'actor_telegram_id|telegram_user_id|user_id|'
    r'telegram_chat_id|chat_id'
    r')'
    r'(?![A-Za-z0-9_])\s*[:=]\s*(?P<value>[0-9]+)(?![A-Za-z0-9_])',
    re.IGNORECASE,
)
_WORKSPACE_CORRELATION_FIELD = re.compile(
    r'(?<![A-Za-z0-9_])workspace_id(?![A-Za-z0-9_])'
    r'\s*[:=]\s*(?P<value>[A-Za-z0-9_-]{1,80})(?![A-Za-z0-9_-])',
    re.IGNORECASE,
)
_SECRET = re.compile(
    r'(?i)\b(password|passwd|pwd|token|api[_-]?key|secret|authorization)'
    r'\s*[:=]\s*[^\s,;]+'
)
_PRIVATE_PATH = re.compile(r'(?<!\w)/(?:root|home|etc|var|opt|srv|mnt)/[^\s,;]+')


class RuntimeIssueEvidenceError(RuntimeError):
    pass


class RuntimeIssueEvidenceInvalid(RuntimeIssueEvidenceError):
    pass


@dataclass(frozen=True)
class RecordedEvidenceLine:
    timestamp: datetime
    text: str


class FixedDockerLogSource:
    def __init__(
        self,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._runner = runner
        self._timeout_seconds = timeout_seconds

    def read(self, *, start: datetime, end: datetime) -> list[RecordedEvidenceLine]:
        try:
            result = self._runner(
                [
                    'docker',
                    'logs',
                    '--timestamps',
                    '--since',
                    start.isoformat(),
                    '--until',
                    end.isoformat(),
                    '--tail',
                    str(MAX_RAW_LINES),
                    'fakturabot',
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeIssueEvidenceError('evidence_source_timeout') from exc
        except OSError as exc:
            raise RuntimeIssueEvidenceError('evidence_source_unavailable') from exc
        if result.returncode != 0:
            raise RuntimeIssueEvidenceError('evidence_source_failed')
        records: list[tuple[datetime | None, int, int, str]] = []
        for stream_order, raw_stream in enumerate((result.stdout, result.stderr)):
            for line_order, line in enumerate(raw_stream.splitlines()[:MAX_RAW_LINES]):
                records.append(
                    (
                        self._timestamp(line),
                        stream_order,
                        line_order,
                        line,
                    )
                )
        records.sort(
            key=lambda record: (
                record[0] is None,
                record[0] or datetime.max.replace(tzinfo=UTC),
                record[1],
                record[2],
            )
        )
        output: list[RecordedEvidenceLine] = []
        used_bytes = 0
        for timestamp, _stream_order, _line_order, line in records[:MAX_RAW_LINES]:
            encoded = line.encode('utf-8', errors='replace')
            record_bytes = len(encoded) + 1
            if used_bytes + record_bytes > MAX_RAW_BYTES:
                break
            used_bytes += record_bytes
            if timestamp is None:
                continue
            match = _TIMESTAMP_LINE.match(line)
            assert match is not None
            output.append(
                RecordedEvidenceLine(
                    timestamp=timestamp,
                    text=match.group(2),
                )
            )
        return output

    @staticmethod
    def _timestamp(line: str) -> datetime | None:
        match = _TIMESTAMP_LINE.match(line)
        if match is None:
            return None
        try:
            timestamp = datetime.fromisoformat(match.group(1).replace('Z', '+00:00'))
            if timestamp.tzinfo is None:
                return None
        except ValueError:
            return None
        return timestamp.astimezone(UTC)


class RuntimeIssueEvidenceService:
    def __init__(self, db_path, *, source: object) -> None:
        self._db_path = db_path
        self._source = source

    def collect(self, *, issue_id: str, handoff_id: str) -> dict[str, object]:
        if not _ISSUE_ID.fullmatch(issue_id) or not _HANDOFF_ID.fullmatch(handoff_id):
            raise RuntimeIssueEvidenceInvalid('evidence_identifier_invalid')
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            validate_runtime_issue_schema(connection)
            validate_runtime_issue_handoff_schema(connection)
            row = connection.execute(
                'SELECT r.issue_id, r.reported_at, r.actor_telegram_id, '
                'r.telegram_chat_id, r.workspace_id, '
                'r.telegram_update_id, r.telegram_message_id, r.reported_build_sha, '
                'h.handoff_id, h.status '
                'FROM runtime_issues AS r '
                'JOIN runtime_issue_handoffs AS h ON h.issue_id = r.issue_id '
                'WHERE r.issue_id = ? AND h.handoff_id = ?',
                (issue_id, handoff_id),
            ).fetchone()
        if row is None:
            raise RuntimeIssueEvidenceInvalid('evidence_issue_handoff_mismatch')
        if str(row['status']) != 'acknowledged':
            raise RuntimeIssueEvidenceInvalid('evidence_handoff_not_acknowledged')
        try:
            reported_at = datetime.fromisoformat(str(row['reported_at']).replace('Z', '+00:00'))
            if reported_at.tzinfo is None:
                raise ValueError
            reported_at = reported_at.astimezone(UTC)
        except ValueError as exc:
            raise RuntimeIssueEvidenceInvalid('evidence_reported_at_invalid') from exc
        start = reported_at - EVIDENCE_WINDOW / 2
        end = reported_at + EVIDENCE_WINDOW / 2
        base = {
            category: {
                'category': category,
                'status': 'unavailable',
                'items': [],
            }
            for category in EVIDENCE_CATEGORIES
        }
        try:
            raw_lines = list(self._source.read(start=start, end=end))
            lines = self._bounded_lines(raw_lines, start=start, end=end)
        except Exception:
            for category in EVIDENCE_CATEGORIES:
                base[category]['status'] = 'source_error'
            lines = []
        for line in lines:
            category = self._category(line.text)
            if category is None:
                continue
            tenant_specific = category in {'stt', 'network', 'provider'}
            correlations = self._correlation_ids(
                line.text,
                update_id=int(row['telegram_update_id']),
                message_id=int(row['telegram_message_id']),
                actor_id=int(row['actor_telegram_id']),
                chat_id=int(row['telegram_chat_id']),
                workspace_id=(
                    str(row['workspace_id'])
                    if row['workspace_id'] is not None
                    else None
                ),
            )
            if tenant_specific and not correlations:
                continue
            excerpt, flags = self._sanitize(line.text)
            item = {
                'source_kind': category,
                'time_start': line.timestamp.isoformat(),
                'time_end': line.timestamp.isoformat(),
                'workspace_scope': (
                    str(row['workspace_id'])
                    if category != 'docker' and row['workspace_id'] is not None
                    else None
                ),
                'correlation_ids': correlations,
                'build_sha': (
                    str(row['reported_build_sha'])
                    if row['reported_build_sha'] is not None
                    else None
                ),
                'sanitized_excerpt': excerpt,
                'content_digest': (
                    'sha256:' + hashlib.sha256(excerpt.encode('utf-8')).hexdigest()
                ),
                'redaction_version': 'runtime-evidence-redaction-v1',
                'redaction_flags': flags,
                'source_reference': f'bounded-{category}-event',
            }
            if sum(len(value['items']) for value in base.values()) >= MAX_ITEMS:
                break
            base[category]['items'].append(item)
            base[category]['status'] = 'available'
        return {
            'schema_version': 'runtime-issue-evidence-v1',
            'issue_id': issue_id,
            'handoff_id': handoff_id,
            'time_start': start.isoformat(),
            'time_end': end.isoformat(),
            'categories': [base[name] for name in EVIDENCE_CATEGORIES],
        }

    @staticmethod
    def _bounded_lines(
        lines: Iterable[RecordedEvidenceLine],
        *,
        start: datetime,
        end: datetime,
    ) -> list[RecordedEvidenceLine]:
        output: list[RecordedEvidenceLine] = []
        used_bytes = 0
        for line in lines:
            if len(output) >= MAX_RAW_LINES:
                break
            timestamp = line.timestamp.astimezone(UTC)
            if not start <= timestamp <= end:
                continue
            encoded = line.text.encode('utf-8', errors='replace')
            record_bytes = len(encoded) + 1
            if used_bytes + record_bytes > MAX_RAW_BYTES:
                break
            used_bytes += record_bytes
            output.append(RecordedEvidenceLine(timestamp=timestamp, text=line.text))
        return output

    @staticmethod
    def _correlation_ids(
        text: str,
        *,
        update_id: int,
        message_id: int,
        actor_id: int,
        chat_id: int,
        workspace_id: str | None,
    ) -> list[str]:
        fields: dict[str, list[int]] = {}
        for match in _NUMERIC_CORRELATION_FIELD.finditer(text):
            fields.setdefault(match.group('label').casefold(), []).append(
                int(match.group('value'))
            )

        def values(*labels: str) -> list[int]:
            return [
                value
                for label in labels
                for value in fields.get(label, [])
            ]

        actor_values = values(
            'actor_telegram_id',
            'telegram_user_id',
            'user_id',
        )
        chat_values = values('telegram_chat_id', 'chat_id')
        workspace_values = [
            match.group('value')
            for match in _WORKSPACE_CORRELATION_FIELD.finditer(text)
        ]
        if actor_values and any(value != actor_id for value in actor_values):
            return []
        if chat_values and any(value != chat_id for value in chat_values):
            return []
        if workspace_values and (
            workspace_id is None
            or any(value != workspace_id for value in workspace_values)
        ):
            return []

        correlations: list[str] = []
        if update_id in values('telegram_update_id', 'update_id', 'update'):
            correlations.append(f'update:{update_id}')
        if message_id in values(
            'telegram_message_id',
            'message_id',
            'message',
        ):
            correlations.append(f'message:{message_id}')
        return correlations

    @staticmethod
    def _category(text: str) -> str | None:
        lowered = text.casefold()
        if any(value in lowered for value in ('stt', 'transcript', 'speech_to_text')):
            return 'stt'
        if any(value in lowered for value in ('container', 'docker', 'health', 'start polling')):
            return 'docker'
        if any(value in lowered for value in ('network', 'connection', 'connect timeout')):
            return 'network'
        if any(value in lowered for value in ('provider', 'http 5', 'http 4', 'api timeout')):
            return 'provider'
        return None

    @staticmethod
    def _sanitize(text: str) -> tuple[str, list[str]]:
        flags: list[str] = []
        sanitized, count = _SECRET.subn(r'\1=[REDACTED]', text)
        if count:
            flags.append('credential_value')
        sanitized, count = _PRIVATE_PATH.subn('[REDACTED PATH]', sanitized)
        if count:
            flags.append('private_path')
        sanitized = ''.join(
            character if ord(character) >= 32 or character == '\t' else ' '
            for character in sanitized
        ).strip()
        if len(sanitized) > MAX_EXCERPT:
            sanitized = sanitized[:MAX_EXCERPT].rstrip()
            flags.append('truncated')
        return sanitized, sorted(set(flags))
