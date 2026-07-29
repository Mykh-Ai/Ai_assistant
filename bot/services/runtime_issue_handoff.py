from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess

from bot.services.db import (
    RUNTIME_ISSUE_HANDOFF_MANIFEST_SCHEMA,
    RUNTIME_ISSUE_HANDOFF_SCHEMA_VERSION,
    managed_connection,
    validate_runtime_issue_handoff_schema,
    validate_runtime_issue_schema,
)


LEASE_DURATION = timedelta(minutes=60)
LEASE_OWNER = 'chatgpt-work-runtime-issue-runner'
WORKSHOP_BRANCH = 'maintenance/runtime-issue-workshop'
HANDOFF_LIMIT_MAX = 3
_HANDOFF_ID = re.compile(r'^RH-[0-9]{8}-[0-9A-F]{12}$')
_COMMIT_SHA = re.compile(r'^[0-9a-f]{40}$')
_DIGEST = re.compile(r'^sha256:[0-9a-f]{64}$')


class RuntimeIssueHandoffError(RuntimeError):
    pass


class RuntimeIssueHandoffInvalid(RuntimeIssueHandoffError):
    pass


class RuntimeIssueHandoffConflict(RuntimeIssueHandoffError):
    pass


@dataclass(frozen=True)
class AckResult:
    handoff_id: str
    status: str
    manifest_digest: str
    workshop_branch: str
    workshop_commit_sha: str
    acknowledged_at: str
    idempotent: bool


def canonical_receipt_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    ).encode('utf-8')


def canonical_receipt_digest(payload: Mapping[str, object]) -> str:
    return f"sha256:{hashlib.sha256(canonical_receipt_json(payload)).hexdigest()}"


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


class FixedRemoteCommitVerifier:
    """Verify a receipt commit is reachable from the fixed remote workshop branch."""

    def __init__(
        self,
        *,
        repository: Path,
        timeout_seconds: float = 15.0,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._repository = repository
        self._timeout_seconds = timeout_seconds
        self._runner = runner

    def __call__(self, branch: str, commit_sha: str) -> bool:
        if branch != WORKSHOP_BRANCH or not _COMMIT_SHA.fullmatch(commit_sha):
            return False
        try:
            fetch = self._runner(
                [
                    'git',
                    '-C',
                    str(self._repository),
                    'fetch',
                    '--no-tags',
                    '--force',
                    'origin',
                    (
                        f'+refs/heads/{WORKSHOP_BRANCH}:'
                        f'refs/remotes/origin/{WORKSHOP_BRANCH}'
                    ),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        if fetch.returncode != 0:
            return False
        try:
            reachable = self._runner(
                [
                    'git',
                    '-C',
                    str(self._repository),
                    'merge-base',
                    '--is-ancestor',
                    commit_sha,
                    f'refs/remotes/origin/{WORKSHOP_BRANCH}',
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                shell=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return reachable.returncode == 0


class RuntimeIssueHandoffService:
    _ISSUE_COLUMNS = (
        'r.issue_id, r.schema_version, r.intake_status, r.description, r.short_title, '
        'r.reported_at, r.actor_telegram_id, r.telegram_update_id, '
        'r.telegram_message_id, r.telegram_chat_id, r.workspace_id, '
        'r.workspace_resolution_reason, r.source_channel, r.active_fsm_state, '
        'r.active_fsm_context_summary_json, r.reported_build_sha, r.build_sha_status, '
        'r.privacy_metadata_json, r.record_version'
    )

    def __init__(
        self,
        db_path: Path,
        *,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
        handoff_id_factory: Callable[[datetime], str] | None = None,
    ) -> None:
        self._db_path = db_path
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._handoff_id_factory = handoff_id_factory or self._new_handoff_id

    def take_next(self, *, limit: int) -> list[dict[str, object]]:
        if not isinstance(limit, int) or not 1 <= limit <= HANDOFF_LIMIT_MAX:
            raise RuntimeIssueHandoffInvalid('handoff_limit_must_be_between_1_and_3')
        now = self._utc_now()
        now_text = now.isoformat()
        lease_until = (now + LEASE_DURATION).isoformat()
        results: list[dict[str, object]] = []
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            validate_runtime_issue_schema(connection)
            validate_runtime_issue_handoff_schema(connection)
            try:
                connection.execute('BEGIN IMMEDIATE')
                connection.execute(
                    "UPDATE runtime_issue_handoffs "
                    "SET status = 'expired_unacknowledged', updated_at = ? "
                    "WHERE status = 'leased' AND lease_until <= ?",
                    (now_text, now_text),
                )
                rows = connection.execute(
                    f'SELECT {self._ISSUE_COLUMNS}, '
                    'h.handoff_id, h.attempt_count, h.manifest_digest '
                    'FROM runtime_issues AS r '
                    'LEFT JOIN runtime_issue_handoffs AS h ON h.issue_id = r.issue_id '
                    "WHERE h.handoff_id IS NULL OR h.status = 'expired_unacknowledged' "
                    'ORDER BY r.reported_at ASC, r.issue_id ASC LIMIT ?',
                    (limit,),
                ).fetchall()
                for row in rows:
                    issue = self._issue_snapshot(row)
                    if row['handoff_id'] is None:
                        handoff_id = self._handoff_id_factory(now)
                        attempt_count = 1
                    else:
                        handoff_id = str(row['handoff_id'])
                        attempt_count = int(row['attempt_count']) + 1
                    durable_payload = {
                        'schema_version': RUNTIME_ISSUE_HANDOFF_MANIFEST_SCHEMA,
                        'handoff_id': handoff_id,
                        'issue': issue,
                    }
                    digest = canonical_receipt_digest(durable_payload)
                    if row['manifest_digest'] is not None and not hmac.compare_digest(
                        str(row['manifest_digest']), digest
                    ):
                        raise RuntimeIssueHandoffConflict('handoff_manifest_digest_drift')
                    raw_token = self._token_factory()
                    if len(raw_token.encode('utf-8')) < 32:
                        raise RuntimeIssueHandoffError('handoff_token_entropy_contract')
                    verifier = token_hash(raw_token)
                    if row['handoff_id'] is None:
                        connection.execute(
                            'INSERT INTO runtime_issue_handoffs ('
                            'handoff_id, issue_id, schema_version, status, lease_token_hash, '
                            'lease_owner, leased_at, lease_until, manifest_schema_version, '
                            'manifest_digest, workshop_branch, workshop_commit_sha, '
                            'acknowledged_at, attempt_count, created_at, updated_at'
                            ') VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?)',
                            (
                                handoff_id,
                                str(row['issue_id']),
                                RUNTIME_ISSUE_HANDOFF_SCHEMA_VERSION,
                                'leased',
                                verifier,
                                LEASE_OWNER,
                                now_text,
                                lease_until,
                                RUNTIME_ISSUE_HANDOFF_MANIFEST_SCHEMA,
                                digest,
                                attempt_count,
                                now_text,
                                now_text,
                            ),
                        )
                    else:
                        connection.execute(
                            "UPDATE runtime_issue_handoffs SET status = 'leased', "
                            'lease_token_hash = ?, lease_owner = ?, leased_at = ?, '
                            'lease_until = ?, attempt_count = ?, updated_at = ? '
                            "WHERE handoff_id = ? AND status = 'expired_unacknowledged'",
                            (
                                verifier,
                                LEASE_OWNER,
                                now_text,
                                lease_until,
                                attempt_count,
                                now_text,
                                handoff_id,
                            ),
                        )
                    results.append(
                        {
                            **durable_payload,
                            'manifest_digest': digest,
                            'generated_at': now_text,
                            'leased_at': now_text,
                            'lease_until': lease_until,
                            'lease_token': raw_token,
                            'attempt_count': attempt_count,
                        }
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return results

    def acknowledge(
        self,
        *,
        handoff_id: str,
        raw_token: str,
        manifest_digest: str,
        workshop_branch: str,
        workshop_commit_sha: str,
        verifier: Callable[[str, str], bool],
    ) -> AckResult:
        if not _HANDOFF_ID.fullmatch(handoff_id):
            raise RuntimeIssueHandoffInvalid('handoff_id_invalid')
        if not _DIGEST.fullmatch(manifest_digest):
            raise RuntimeIssueHandoffInvalid('manifest_digest_invalid')
        if workshop_branch != WORKSHOP_BRANCH:
            raise RuntimeIssueHandoffInvalid('workshop_branch_invalid')
        if not _COMMIT_SHA.fullmatch(workshop_commit_sha):
            raise RuntimeIssueHandoffInvalid('workshop_commit_invalid')
        supplied_hash = token_hash(raw_token)
        now = self._utc_now()
        now_text = now.isoformat()
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            validate_runtime_issue_handoff_schema(connection)
            row = self._ack_row(connection, handoff_id)
            idempotent = self._validate_ack_row(
                row,
                supplied_hash=supplied_hash,
                manifest_digest=manifest_digest,
                workshop_branch=workshop_branch,
                workshop_commit_sha=workshop_commit_sha,
                now_text=now_text,
            )
            if idempotent is not None:
                return idempotent

        if not verifier(workshop_branch, workshop_commit_sha):
            raise RuntimeIssueHandoffConflict('workshop_receipt_not_verified')

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            validate_runtime_issue_handoff_schema(connection)
            try:
                connection.execute('BEGIN IMMEDIATE')
                row = self._ack_row(connection, handoff_id)
                idempotent = self._validate_ack_row(
                    row,
                    supplied_hash=supplied_hash,
                    manifest_digest=manifest_digest,
                    workshop_branch=workshop_branch,
                    workshop_commit_sha=workshop_commit_sha,
                    now_text=now_text,
                )
                if idempotent is not None:
                    connection.commit()
                    return idempotent
                lease_until = str(row['lease_until'])
                cursor = connection.execute(
                    "UPDATE runtime_issue_handoffs SET status = 'acknowledged', "
                    'workshop_branch = ?, workshop_commit_sha = ?, acknowledged_at = ?, '
                    'updated_at = ? WHERE handoff_id = ? AND status = \'leased\' '
                    'AND lease_owner = ? AND lease_token_hash = ? '
                    'AND manifest_digest = ? AND lease_until = ? AND lease_until > ?',
                    (
                        workshop_branch,
                        workshop_commit_sha,
                        now_text,
                        now_text,
                        handoff_id,
                        LEASE_OWNER,
                        supplied_hash,
                        manifest_digest,
                        lease_until,
                        now_text,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeIssueHandoffConflict('handoff_ack_race')
                connection.commit()
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise
        return AckResult(
            handoff_id=handoff_id,
            status='acknowledged',
            manifest_digest=manifest_digest,
            workshop_branch=workshop_branch,
            workshop_commit_sha=workshop_commit_sha,
            acknowledged_at=now_text,
            idempotent=False,
        )

    @staticmethod
    def _ack_row(
        connection: sqlite3.Connection,
        handoff_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            'SELECT handoff_id, status, lease_token_hash, lease_owner, leased_at, '
            'lease_until, manifest_digest, workshop_branch, workshop_commit_sha, '
            'acknowledged_at FROM runtime_issue_handoffs WHERE handoff_id = ?',
            (handoff_id,),
        ).fetchone()

    @staticmethod
    def _validate_ack_row(
        row: sqlite3.Row | None,
        *,
        supplied_hash: str,
        manifest_digest: str,
        workshop_branch: str,
        workshop_commit_sha: str,
        now_text: str,
    ) -> AckResult | None:
        if row is None:
            raise RuntimeIssueHandoffInvalid('handoff_not_found')
        handoff_id = str(row['handoff_id'])
        if str(row['status']) == 'acknowledged':
            same = (
                hmac.compare_digest(str(row['lease_token_hash']), supplied_hash)
                and hmac.compare_digest(str(row['manifest_digest']), manifest_digest)
                and str(row['workshop_branch']) == workshop_branch
                and str(row['workshop_commit_sha']) == workshop_commit_sha
            )
            if not same:
                raise RuntimeIssueHandoffConflict('handoff_ack_conflict')
            return AckResult(
                handoff_id=handoff_id,
                status='acknowledged',
                manifest_digest=manifest_digest,
                workshop_branch=workshop_branch,
                workshop_commit_sha=workshop_commit_sha,
                acknowledged_at=str(row['acknowledged_at']),
                idempotent=True,
            )
        if str(row['status']) != 'leased':
            raise RuntimeIssueHandoffConflict('handoff_not_live')
        if str(row['lease_owner']) != LEASE_OWNER or not str(row['leased_at']):
            raise RuntimeIssueHandoffConflict('handoff_lease_owner_mismatch')
        if str(row['lease_until']) <= now_text:
            raise RuntimeIssueHandoffConflict('handoff_lease_expired')
        if not hmac.compare_digest(str(row['lease_token_hash']), supplied_hash):
            raise RuntimeIssueHandoffConflict('handoff_token_mismatch')
        if not hmac.compare_digest(str(row['manifest_digest']), manifest_digest):
            raise RuntimeIssueHandoffConflict('handoff_digest_mismatch')
        return None

    @staticmethod
    def _issue_snapshot(row: sqlite3.Row) -> dict[str, object]:
        try:
            context = json.loads(str(row['active_fsm_context_summary_json']))
            if not isinstance(context, dict):
                raise ValueError
            context_status = 'active' if row['active_fsm_state'] is not None else 'not_active'
        except (TypeError, ValueError, json.JSONDecodeError):
            context = {}
            context_status = 'read_failed'
        try:
            privacy = json.loads(str(row['privacy_metadata_json']))
            if not isinstance(privacy, dict):
                raise ValueError
        except (TypeError, ValueError, json.JSONDecodeError):
            privacy = {}
        return {
            'issue_id': str(row['issue_id']),
            'schema_version': int(row['schema_version']),
            'intake_status': str(row['intake_status']),
            'record_version': int(row['record_version']),
            'description': str(row['description']),
            'short_title': str(row['short_title']),
            'reported_at': str(row['reported_at']),
            'actor_telegram_id': int(row['actor_telegram_id']),
            'telegram_update_id': int(row['telegram_update_id']),
            'telegram_message_id': int(row['telegram_message_id']),
            'telegram_chat_id': int(row['telegram_chat_id']),
            'workspace_id': (
                str(row['workspace_id']) if row['workspace_id'] is not None else None
            ),
            'workspace_resolution_reason': str(row['workspace_resolution_reason']),
            'source_channel': str(row['source_channel']),
            'active_fsm_state': (
                str(row['active_fsm_state'])
                if row['active_fsm_state'] is not None
                else None
            ),
            'fsm_context_status': context_status,
            'active_fsm_context_summary': context,
            'reported_build_sha': (
                str(row['reported_build_sha'])
                if row['reported_build_sha'] is not None
                else None
            ),
            'build_sha_status': str(row['build_sha_status']),
            'privacy_metadata': privacy,
        }

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise RuntimeIssueHandoffError('handoff_clock_must_be_timezone_aware')
        return value.astimezone(UTC)

    @staticmethod
    def _new_handoff_id(now: datetime) -> str:
        return f'RH-{now.astimezone(UTC):%Y%m%d}-{secrets.token_hex(6).upper()}'
