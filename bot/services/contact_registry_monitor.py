from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any, Literal, Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Config
from bot.services.db import managed_connection
from bot.services.slovak_company_registry import (
    RegistryCompanyCandidate,
    RegistryCompanyDetails,
    RegistryLookupError,
    SlovakCompanyRegistry,
)
from bot.services.slovak_tax_registry import (
    SlovakCompanyDetailsAggregator,
    SlovakTaxRegistry,
    verified_financna_sprava_schema,
)
from bot.services.workspace_context import (
    WorkspaceContext,
    WorkspaceContextError,
    WorkspaceContextService,
)


logger = logging.getLogger(__name__)
CALLBACK_PREFIX = 'contact_monitor'
DECISION_YES = 'yes'
DECISION_NO = 'no'
_MONITORED_FIELDS = ('name', 'address', 'dic', 'ic_dph')


CONTACT_REGISTRY_MONITOR_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS contact_registry_monitor_state (
    contact_id INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    subject_id TEXT,
    last_checked_at TEXT,
    next_check_at TEXT NOT NULL,
    last_result_hash TEXT,
    last_error_code TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CONTACT_REGISTRY_CHANGE_PROPOSAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS contact_registry_change_proposal (
    proposal_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    actor_telegram_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    subject_id TEXT NOT NULL,
    contact_updated_at TEXT NOT NULL,
    ico TEXT NOT NULL,
    old_values_json TEXT NOT NULL,
    new_values_json TEXT NOT NULL,
    changed_fields_json TEXT NOT NULL,
    provider_sources_json TEXT NOT NULL,
    status TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    notified_at TEXT,
    resolved_at TEXT,
    expires_at TEXT NOT NULL,
    notification_attempts INTEGER NOT NULL DEFAULT 0,
    last_notification_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def ensure_contact_registry_monitor_schema(connection: sqlite3.Connection) -> None:
    connection.execute(CONTACT_REGISTRY_MONITOR_STATE_SCHEMA)
    connection.execute(CONTACT_REGISTRY_CHANGE_PROPOSAL_SCHEMA)
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_contact_registry_monitor_due '
        'ON contact_registry_monitor_state(next_check_at)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_contact_registry_proposal_pending '
        'ON contact_registry_change_proposal(workspace_id, status, expires_at)'
    )


@dataclass(frozen=True)
class MonitoredContact:
    contact_id: int
    workspace_id: str
    actor_telegram_id: int
    name: str
    ico: str
    dic: str
    ic_dph: str | None
    address: str
    updated_at: str


@dataclass(frozen=True)
class ContactRegistryChangeProposal:
    proposal_id: str
    workspace_id: str
    actor_telegram_id: int
    contact_id: int
    contact_updated_at: str
    ico: str
    old_values: dict[str, str | None]
    new_values: dict[str, str | None]
    changed_fields: tuple[str, ...]
    provider_sources: tuple[str, ...]
    status: str
    expires_at: datetime


@dataclass(frozen=True)
class ContactMonitorRunResult:
    eligible_contacts: int = 0
    checked_contacts: int = 0
    proposals_created: int = 0
    notifications_sent: int = 0
    unchanged_contacts: int = 0
    skipped_contacts: int = 0
    failed_checks: int = 0
    failed_notifications: int = 0


@dataclass(frozen=True)
class ProposalResolution:
    status: Literal[
        'applied', 'dismissed', 'stale', 'expired', 'conflict', 'forbidden', 'missing'
    ]
    contact_name: str | None = None
    reason: str | None = None


class RegistrySearchProvider(Protocol):
    async def search(
        self, query: str, *, only_active: bool = True
    ) -> list[RegistryCompanyCandidate]:
        ...


class RegistryDetailsProvider(Protocol):
    async def get_details(self, subject_id: str) -> Any:
        ...


def _utc_now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _utc_now(value).replace(microsecond=0).isoformat()


def next_monitor_slot(
    *,
    now: datetime,
    timezone_name: str,
    anchor: str,
    interval_days: int,
    include_current: bool = False,
) -> datetime:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError('contact_monitor_timezone_invalid') from exc
    try:
        anchor_local = datetime.fromisoformat(anchor)
    except ValueError as exc:
        raise ValueError('contact_monitor_anchor_invalid') from exc
    if anchor_local.tzinfo is not None:
        raise ValueError('contact_monitor_anchor_must_be_local')
    if interval_days <= 0:
        raise ValueError('contact_monitor_interval_invalid')
    anchor_local = anchor_local.replace(tzinfo=zone)
    current_local = _utc_now(now).astimezone(zone)
    if current_local < anchor_local:
        return anchor_local.astimezone(timezone.utc)
    elapsed_days = (current_local.date() - anchor_local.date()).days
    steps = elapsed_days // interval_days
    candidate = anchor_local + timedelta(days=steps * interval_days)
    if candidate < current_local or (candidate == current_local and not include_current):
        candidate += timedelta(days=interval_days)
    return candidate.astimezone(timezone.utc)


def monitor_has_started(*, now: datetime, timezone_name: str, anchor: str) -> bool:
    zone = ZoneInfo(timezone_name)
    anchor_local = datetime.fromisoformat(anchor).replace(tzinfo=zone)
    return _utc_now(now) >= anchor_local.astimezone(timezone.utc)


class ContactRegistryMonitorService:
    def __init__(self, db_path: Path, config: Config) -> None:
        self._db_path = db_path
        self._config = config

    def list_due_contacts(
        self, *, now: datetime, include_not_due: bool = False
    ) -> list[MonitoredContact]:
        if not include_not_due and not monitor_has_started(
            now=now,
            timezone_name=self._config.contact_registry_monitor_timezone,
            anchor=self._config.contact_registry_monitor_anchor,
        ):
            return []
        now_text = _iso(now)
        with managed_connection(self._db_path) as connection:
            ensure_contact_registry_monitor_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT c.id, c.workspace_id, c.supplier_telegram_id, c.name, c.ico,
                       c.dic, c.ic_dph, c.address, c.updated_at
                FROM contact c
                JOIN workspace w ON w.workspace_id = c.workspace_id
                JOIN workspace_membership m
                  ON m.workspace_id = c.workspace_id
                 AND m.telegram_id = c.supplier_telegram_id
                JOIN authorized_users a ON a.telegram_id = c.supplier_telegram_id
                JOIN supplier s
                  ON s.workspace_id = c.workspace_id
                 AND s.telegram_id = c.supplier_telegram_id
                LEFT JOIN contact_registry_monitor_state cms ON cms.contact_id = c.id
                WHERE c.workspace_id IS NOT NULL
                  AND a.status = 'active'
                  AND (? = 1 OR cms.contact_id IS NULL OR cms.next_check_at <= ?)
                  AND NOT EXISTS (
                    SELECT 1 FROM contact_registry_change_proposal p
                    WHERE p.contact_id = c.id AND p.workspace_id = c.workspace_id
                      AND p.status = 'pending' AND p.expires_at > ?
                  )
                ORDER BY c.id
                LIMIT ?
                """,
                (
                    1 if include_not_due else 0,
                    now_text,
                    now_text,
                    self._config.contact_registry_monitor_batch_size,
                ),
            ).fetchall()
        result: list[MonitoredContact] = []
        for row in rows:
            ico = re.sub(r'\s+', '', str(row['ico'] or ''))
            if not re.fullmatch(r'\d{8}', ico):
                continue
            result.append(
                MonitoredContact(
                    contact_id=int(row['id']),
                    workspace_id=str(row['workspace_id']),
                    actor_telegram_id=int(row['supplier_telegram_id']),
                    name=str(row['name']),
                    ico=ico,
                    dic=str(row['dic'] or ''),
                    ic_dph=str(row['ic_dph']) if row['ic_dph'] else None,
                    address=str(row['address']),
                    updated_at=str(row['updated_at']),
                )
            )
        return result

    def record_failure(self, contact: MonitoredContact, *, now: datetime, code: str) -> None:
        bounded_code = re.sub(r'[^a-z0-9_:-]', '_', code.casefold())[:100] or 'unknown'
        self._upsert_state(
            contact,
            now=now,
            subject_id=None,
            result_hash=None,
            error_code=bounded_code,
            failed=True,
        )

    def record_unchanged(
        self,
        contact: MonitoredContact,
        *,
        now: datetime,
        details: RegistryCompanyDetails,
    ) -> None:
        self._upsert_state(
            contact,
            now=now,
            subject_id=details.subject_id,
            result_hash=_bounded_result_hash(details),
            error_code=None,
            failed=False,
        )

    def create_proposal(
        self,
        context: WorkspaceContext,
        contact: MonitoredContact,
        *,
        now: datetime,
        details: RegistryCompanyDetails,
    ) -> ContactRegistryChangeProposal | None:
        if context.workspace_id != contact.workspace_id:
            raise ValueError('contact_monitor_workspace_mismatch')
        old_values, new_values, changed_fields = _build_change_set(contact, details)
        if not changed_fields:
            self.record_unchanged(contact, now=now, details=details)
            return None
        proposal_id = str(uuid4())
        detected_at = _utc_now(now)
        expires_at = detected_at + timedelta(
            days=self._config.contact_registry_monitor_proposal_ttl_days
        )
        with managed_connection(self._db_path) as connection:
            ensure_contact_registry_monitor_schema(connection)
            connection.execute('BEGIN IMMEDIATE')
            duplicate = connection.execute(
                "SELECT 1 FROM contact_registry_change_proposal "
                "WHERE contact_id=? AND workspace_id=? AND status='pending' AND expires_at>?",
                (contact.contact_id, contact.workspace_id, _iso(now)),
            ).fetchone()
            if duplicate is not None:
                connection.rollback()
                return None
            connection.execute(
                """
                INSERT INTO contact_registry_change_proposal (
                    proposal_id, workspace_id, actor_telegram_id, contact_id,
                    subject_id, contact_updated_at, ico, old_values_json,
                    new_values_json, changed_fields_json, provider_sources_json,
                    status, detected_at, expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    contact.workspace_id,
                    context.actor_telegram_id,
                    contact.contact_id,
                    details.subject_id,
                    contact.updated_at,
                    contact.ico,
                    json.dumps(old_values, ensure_ascii=False, sort_keys=True),
                    json.dumps(new_values, ensure_ascii=False, sort_keys=True),
                    json.dumps(changed_fields),
                    json.dumps(details.provider_sources),
                    _iso(detected_at),
                    _iso(expires_at),
                    _iso(detected_at),
                    _iso(detected_at),
                ),
            )
            self._upsert_state_connection(
                connection,
                contact,
                now=now,
                subject_id=details.subject_id,
                result_hash=_bounded_result_hash(details),
                error_code=None,
                failed=False,
            )
            connection.commit()
        return ContactRegistryChangeProposal(
            proposal_id=proposal_id,
            workspace_id=contact.workspace_id,
            actor_telegram_id=context.actor_telegram_id,
            contact_id=contact.contact_id,
            contact_updated_at=contact.updated_at,
            ico=contact.ico,
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields,
            provider_sources=details.provider_sources,
            status='pending',
            expires_at=expires_at,
        )

    def mark_notification(
        self, proposal_id: str, *, now: datetime, error_code: str | None
    ) -> None:
        with managed_connection(self._db_path) as connection:
            ensure_contact_registry_monitor_schema(connection)
            connection.execute(
                """
                UPDATE contact_registry_change_proposal
                SET notification_attempts=notification_attempts+1,
                    notified_at=CASE WHEN ? IS NULL THEN ? ELSE notified_at END,
                    last_notification_error=?, updated_at=?
                WHERE proposal_id=? AND status='pending'
                """,
                (
                    error_code,
                    _iso(now),
                    error_code[:100] if error_code else None,
                    _iso(now),
                    proposal_id,
                ),
            )
            connection.commit()

    def resolve(
        self,
        *,
        proposal_id: str,
        actor_telegram_id: int,
        decision: str,
        now: datetime,
    ) -> ProposalResolution:
        with managed_connection(self._db_path) as connection:
            ensure_contact_registry_monitor_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute(
                'SELECT * FROM contact_registry_change_proposal WHERE proposal_id=?',
                (proposal_id,),
            ).fetchone()
            if row is None:
                connection.rollback()
                return ProposalResolution('missing', reason='proposal_missing')
            if int(row['actor_telegram_id']) != actor_telegram_id:
                connection.rollback()
                return ProposalResolution('forbidden', reason='actor_mismatch')
            prior_status = str(row['status'])
            if prior_status != 'pending':
                connection.rollback()
                if prior_status == 'expired':
                    return ProposalResolution('expired', reason='proposal_already_expired')
                if prior_status == 'conflict':
                    return ProposalResolution('conflict', reason='proposal_already_conflict')
                reason = (
                    f'proposal_already_{prior_status}'
                    if prior_status in {'applied', 'dismissed', 'stale'}
                    else 'proposal_status_invalid'
                )
                return ProposalResolution('stale', reason=reason)
            if str(row['expires_at']) <= _iso(now):
                connection.execute(
                    "UPDATE contact_registry_change_proposal SET status='expired', "
                    'resolved_at=?, updated_at=? WHERE proposal_id=?',
                    (_iso(now), _iso(now), proposal_id),
                )
                connection.commit()
                return ProposalResolution('expired', reason='proposal_expired')
            if not _authorized_actor_workspace_owner(
                connection,
                actor_telegram_id=actor_telegram_id,
                workspace_id=str(row['workspace_id']),
            ):
                connection.rollback()
                return ProposalResolution('forbidden', reason='workspace_not_authorized')
            if decision == DECISION_NO:
                connection.execute(
                    "UPDATE contact_registry_change_proposal SET status='dismissed', "
                    'resolved_at=?, updated_at=? WHERE proposal_id=?',
                    (_iso(now), _iso(now), proposal_id),
                )
                connection.commit()
                return ProposalResolution('dismissed')
            if decision != DECISION_YES:
                connection.rollback()
                return ProposalResolution('stale', reason='decision_invalid')

            contact = connection.execute(
                'SELECT * FROM contact WHERE id=? AND workspace_id=?',
                (int(row['contact_id']), str(row['workspace_id'])),
            ).fetchone()
            old_values = json.loads(str(row['old_values_json']))
            new_values = json.loads(str(row['new_values_json']))
            stale_reason: str | None = None
            if contact is None:
                stale_reason = 'contact_missing'
            elif str(contact['ico']) != str(row['ico']):
                stale_reason = 'contact_ico_changed'
            elif str(contact['updated_at']) != str(row['contact_updated_at']):
                stale_reason = 'contact_version_changed'
            elif any(contact[field] != old_values[field] for field in _MONITORED_FIELDS):
                stale_reason = 'contact_values_changed'
            if stale_reason is not None:
                connection.execute(
                    "UPDATE contact_registry_change_proposal SET status='stale', "
                    'resolved_at=?, updated_at=? WHERE proposal_id=?',
                    (_iso(now), _iso(now), proposal_id),
                )
                connection.commit()
                return ProposalResolution('stale', reason=stale_reason)
            if _contact_conflict(
                connection,
                workspace_id=str(row['workspace_id']),
                contact_id=int(row['contact_id']),
                name=str(new_values['name']),
                ico=str(row['ico']),
            ):
                connection.execute(
                    "UPDATE contact_registry_change_proposal SET status='conflict', "
                    'resolved_at=?, updated_at=? WHERE proposal_id=?',
                    (_iso(now), _iso(now), proposal_id),
                )
                connection.commit()
                return ProposalResolution('conflict', reason='contact_identity_conflict')
            connection.execute(
                """
                UPDATE contact SET name=?, address=?, dic=?, ic_dph=?,
                    updated_at=?
                WHERE id=? AND workspace_id=?
                """,
                (
                    new_values['name'],
                    new_values['address'],
                    new_values['dic'],
                    new_values['ic_dph'],
                    _iso(now),
                    int(row['contact_id']),
                    str(row['workspace_id']),
                ),
            )
            connection.execute(
                "UPDATE contact_registry_change_proposal SET status='applied', "
                'resolved_at=?, updated_at=? WHERE proposal_id=?',
                (_iso(now), _iso(now), proposal_id),
            )
            connection.commit()
            return ProposalResolution('applied', contact_name=str(new_values['name']))

    def _upsert_state(
        self,
        contact: MonitoredContact,
        *,
        now: datetime,
        subject_id: str | None,
        result_hash: str | None,
        error_code: str | None,
        failed: bool,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            ensure_contact_registry_monitor_schema(connection)
            self._upsert_state_connection(
                connection,
                contact,
                now=now,
                subject_id=subject_id,
                result_hash=result_hash,
                error_code=error_code,
                failed=failed,
            )
            connection.commit()

    def _upsert_state_connection(
        self,
        connection: sqlite3.Connection,
        contact: MonitoredContact,
        *,
        now: datetime,
        subject_id: str | None,
        result_hash: str | None,
        error_code: str | None,
        failed: bool,
    ) -> None:
        next_check = next_monitor_slot(
            now=now,
            timezone_name=self._config.contact_registry_monitor_timezone,
            anchor=self._config.contact_registry_monitor_anchor,
            interval_days=self._config.contact_registry_monitor_interval_days,
        )
        connection.execute(
            """
            INSERT INTO contact_registry_monitor_state (
                contact_id, workspace_id, subject_id, last_checked_at,
                next_check_at, last_result_hash, last_error_code,
                consecutive_failures, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(contact_id) DO UPDATE SET
                workspace_id=excluded.workspace_id,
                subject_id=COALESCE(excluded.subject_id, subject_id),
                last_checked_at=excluded.last_checked_at,
                next_check_at=excluded.next_check_at,
                last_result_hash=COALESCE(excluded.last_result_hash, last_result_hash),
                last_error_code=excluded.last_error_code,
                consecutive_failures=CASE WHEN excluded.last_error_code IS NULL
                    THEN 0 ELSE consecutive_failures + 1 END,
                updated_at=excluded.updated_at
            """,
            (
                contact.contact_id,
                contact.workspace_id,
                subject_id,
                _iso(now),
                _iso(next_check),
                result_hash,
                error_code,
                1 if failed else 0,
                _iso(now),
                _iso(now),
            ),
        )


def _authorized_actor_workspace_owner(
    connection: sqlite3.Connection, *, actor_telegram_id: int, workspace_id: str
) -> bool:
    return connection.execute(
        """
        SELECT 1 FROM workspace w
        JOIN workspace_membership m ON m.workspace_id=w.workspace_id
        JOIN authorized_users a ON a.telegram_id=m.telegram_id
        JOIN supplier s ON s.workspace_id=w.workspace_id AND s.telegram_id=m.telegram_id
        WHERE w.workspace_id=? AND m.telegram_id=? AND a.status='active'
        """,
        (workspace_id, actor_telegram_id),
    ).fetchone() is not None


def _contact_conflict(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    contact_id: int,
    name: str,
    ico: str,
) -> bool:
    return connection.execute(
        """
        SELECT 1 FROM contact
        WHERE workspace_id=? AND id<>? AND (name=? OR ico=?)
        """,
        (workspace_id, contact_id, name, ico),
    ).fetchone() is not None


def _normalize_value(field: str, value: str | None) -> str:
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    if field in {'dic', 'ic_dph'}:
        return re.sub(r'\s+', '', text).upper()
    return text.casefold()


def _build_change_set(
    contact: MonitoredContact, details: RegistryCompanyDetails
) -> tuple[dict[str, str | None], dict[str, str | None], tuple[str, ...]]:
    old_values: dict[str, str | None] = {
        'name': contact.name,
        'address': contact.address,
        'dic': contact.dic,
        'ic_dph': contact.ic_dph,
    }
    new_values: dict[str, str | None] = {
        'name': details.name,
        'address': details.address or contact.address,
        'dic': details.dic or contact.dic,
        'ic_dph': details.ic_dph or contact.ic_dph,
    }
    changed = tuple(
        field
        for field in _MONITORED_FIELDS
        if _normalize_value(field, old_values[field])
        != _normalize_value(field, new_values[field])
    )
    return old_values, new_values, changed


def _bounded_result_hash(details: RegistryCompanyDetails) -> str:
    import hashlib

    bounded = json.dumps(
        {
            'subject_id': details.subject_id,
            'name': details.name,
            'ico': details.ico,
            'dic': details.dic,
            'ic_dph': details.ic_dph,
            'address': details.address,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(bounded.encode('utf-8')).hexdigest()


def proposal_keyboard(proposal_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Aktualizovať kontakt',
                    callback_data=f'{CALLBACK_PREFIX}:{DECISION_YES}:{proposal_id}',
                ),
                InlineKeyboardButton(
                    text='Ponechať bez zmeny',
                    callback_data=f'{CALLBACK_PREFIX}:{DECISION_NO}:{proposal_id}',
                ),
            ]
        ]
    )


def format_change_notification(proposal: ContactRegistryChangeProposal) -> str:
    labels = {'name': 'Názov', 'address': 'Sídlo', 'dic': 'DIČ', 'ic_dph': 'IČ DPH'}
    lines = [
        'V oficiálnom registri som našiel zmenu kontaktu:',
        f'Kontakt: {proposal.old_values["name"] or "—"}',
        f'IČO: {proposal.ico}',
    ]
    for field in proposal.changed_fields:
        old = proposal.old_values[field] or '—'
        new = proposal.new_values[field] or '—'
        lines.extend((f'\n{labels[field]}:', f'• pôvodne: {old}', f'• aktuálne: {new}'))
    lines.append('\nUž vystavené faktúry ani ich PDF sa nezmenia.')
    lines.append('Chcete aktualizovať kontakt v databáze?')
    return '\n'.join(lines)


async def send_contact_registry_monitor_once(
    *,
    bot: Any | None,
    config: Config,
    now: datetime | None = None,
    persist: bool = True,
    search_provider: RegistrySearchProvider | None = None,
    details_provider: RegistryDetailsProvider | None = None,
    include_not_due: bool = False,
) -> ContactMonitorRunResult:
    run_now = _utc_now(now)
    service = ContactRegistryMonitorService(config.db_path, config)
    contacts = service.list_due_contacts(
        now=run_now, include_not_due=include_not_due
    )
    search = search_provider or SlovakCompanyRegistry(
        timeout_seconds=config.contact_registry_timeout_seconds,
        max_results=config.contact_registry_max_results,
    )
    if details_provider is None:
        registry = search if isinstance(search, SlovakCompanyRegistry) else SlovakCompanyRegistry(
            timeout_seconds=config.contact_registry_timeout_seconds,
            max_results=config.contact_registry_max_results,
        )
        tax = SlovakTaxRegistry(
            enabled=config.contact_tax_lookup_enabled,
            api_key=config.financna_sprava_api_key,
            schema=verified_financna_sprava_schema(),
            timeout_seconds=config.financna_sprava_timeout_seconds,
        )
        details_provider = SlovakCompanyDetailsAggregator(registry, tax)
    context_service = WorkspaceContextService(config.db_path)
    counts = {
        'eligible_contacts': len(contacts),
        'checked_contacts': 0,
        'proposals_created': 0,
        'notifications_sent': 0,
        'unchanged_contacts': 0,
        'skipped_contacts': 0,
        'failed_checks': 0,
        'failed_notifications': 0,
    }
    for contact in contacts:
        try:
            context = context_service.resolve_for_background_workspace(
                contact.workspace_id, include_inactive=True
            )
            if context.actor_telegram_id != contact.actor_telegram_id:
                raise WorkspaceContextError('contact_monitor_actor_mismatch')
        except WorkspaceContextError:
            counts['skipped_contacts'] += 1
            if persist:
                service.record_failure(contact, now=run_now, code='workspace_unauthorized')
            continue
        try:
            candidates = await search.search(contact.ico, only_active=False)
            exact = [candidate for candidate in candidates if candidate.ico == contact.ico]
            if len(exact) != 1:
                raise RegistryLookupError('registry_exact_ico_not_unique')
            aggregated = await details_provider.get_details(exact[0].subject_id)
            details = getattr(aggregated, 'details', aggregated)
            if details.ico != contact.ico:
                raise RegistryLookupError('registry_exact_ico_mismatch')
            counts['checked_contacts'] += 1
        except Exception as exc:
            counts['failed_checks'] += 1
            if persist:
                service.record_failure(
                    contact,
                    now=run_now,
                    code=str(exc) if isinstance(exc, RegistryLookupError) else 'registry_check_failed',
                )
            continue
        old_values, new_values, changed = _build_change_set(contact, details)
        if not changed:
            counts['unchanged_contacts'] += 1
            if persist:
                service.record_unchanged(contact, now=run_now, details=details)
            continue
        if not persist:
            counts['proposals_created'] += 1
            continue
        proposal = service.create_proposal(context, contact, now=run_now, details=details)
        if proposal is None:
            counts['skipped_contacts'] += 1
            continue
        counts['proposals_created'] += 1
        if bot is None:
            continue
        try:
            await bot.send_message(
                context.actor_telegram_id,
                format_change_notification(proposal),
                reply_markup=proposal_keyboard(proposal.proposal_id),
            )
        except Exception:
            counts['failed_notifications'] += 1
            service.mark_notification(
                proposal.proposal_id, now=run_now, error_code='telegram_send_failed'
            )
            logger.exception(
                'Contact registry monitor notification failed proposal_id=%s workspace_id=%s',
                proposal.proposal_id,
                contact.workspace_id,
            )
        else:
            counts['notifications_sent'] += 1
            service.mark_notification(proposal.proposal_id, now=run_now, error_code=None)
    return ContactMonitorRunResult(**counts)


async def run_contact_registry_monitor_scheduler(*, bot: Any, config: Config) -> None:
    if not config.contact_registry_monitor_enabled:
        logger.info('Contact registry monitor disabled by configuration')
        return
    if not config.contact_registry_lookup_enabled:
        logger.warning('Contact registry monitor requires registry lookup to be enabled')
        return
    logger.info(
        'Contact registry monitor started interval_days=%s timezone=%s anchor=%s',
        config.contact_registry_monitor_interval_days,
        config.contact_registry_monitor_timezone,
        config.contact_registry_monitor_anchor,
    )
    while True:
        try:
            result = await send_contact_registry_monitor_once(
                bot=bot, config=config, persist=True
            )
            if result.checked_contacts or result.failed_checks or result.skipped_contacts:
                logger.info(
                    'Contact registry monitor tick eligible=%s checked=%s proposals=%s '
                    'notified=%s unchanged=%s skipped=%s failed=%s send_failed=%s',
                    result.eligible_contacts,
                    result.checked_contacts,
                    result.proposals_created,
                    result.notifications_sent,
                    result.unchanged_contacts,
                    result.skipped_contacts,
                    result.failed_checks,
                    result.failed_notifications,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Contact registry monitor tick failed')
        await asyncio.sleep(300)
