from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from bot.config import Config
from bot.services.contact_registry_monitor import (
    ContactRegistryChangeProposal,
    ContactRegistryMonitorService,
    MonitoredContact,
    format_change_notification,
    next_monitor_slot,
    proposal_keyboard,
    send_contact_registry_monitor_once,
)
from bot.services.db import init_db
from bot.services.slovak_company_registry import (
    RegistryCompanyCandidate,
    RegistryCompanyDetails,
)


NOW = datetime(2026, 8, 3, 1, 0, tzinfo=timezone.utc)


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='test',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path / 'storage',
        contact_registry_lookup_enabled=True,
        contact_registry_monitor_enabled=True,
        contact_registry_monitor_anchor='2026-08-03T03:00:00',
        contact_registry_monitor_timezone='Europe/Bratislava',
        contact_registry_monitor_interval_days=14,
    )


def _seed(config: Config, *, pdf_path: Path | None = None) -> MonitoredContact:
    init_db(config.db_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            "INSERT INTO authorized_users "
            "(telegram_id, role, status, created_at) VALUES (111, 'user', 'active', ?)",
            ('2026-08-01T00:00:00+00:00',),
        )
        connection.execute(
            "INSERT INTO workspace "
            "(workspace_id, display_name, storage_key, drive_folder_name, status, "
            "created_at, updated_at) VALUES "
            "('ws-1', 'Test', 'ws-1', 'Test', 'active', ?, ?)",
            ('2026-08-01T00:00:00+00:00', '2026-08-01T00:00:00+00:00'),
        )
        connection.execute(
            "INSERT INTO workspace_membership "
            "(workspace_id, telegram_id, role, status, created_at, updated_at) "
            "VALUES ('ws-1', 111, 'owner', 'active', ?, ?)",
            ('2026-08-01T00:00:00+00:00', '2026-08-01T00:00:00+00:00'),
        )
        connection.execute(
            "INSERT INTO supplier "
            "(workspace_id, telegram_id, name, ico, dic, address, iban, swift, "
            "email, days_due) VALUES "
            "('ws-1', 111, 'Supplier', '12345678', '1234567890', 'Old', "
            "'SK000', 'TEST', 'a@example.test', 14)"
        )
        cursor = connection.execute(
            "INSERT INTO contact "
            "(workspace_id, supplier_telegram_id, name, ico, dic, ic_dph, address, "
            "email, source_type, updated_at) VALUES "
            "('ws-1', 111, 'Tech Company s.r.o.', '87654321', '2020202020', "
            "'SK2020202020', 'Old address', 'contact@example.test', 'manual', ?)",
            ('2026-08-01T10:00:00+00:00',),
        )
        contact_id = int(cursor.lastrowid)
        if pdf_path is not None:
            connection.execute(
                "INSERT INTO invoice "
                "(workspace_id, supplier_telegram_id, contact_id, invoice_number, "
                "issue_date, delivery_date, due_date, due_days, total_amount, currency, "
                "status, pdf_path, updated_at) VALUES "
                "('ws-1', 111, ?, '2026001', '2026-07-01', '2026-07-01', "
                "'2026-07-15', 14, 100, 'EUR', 'issued', ?, ?)",
                (contact_id, str(pdf_path), '2026-07-01T00:00:00+00:00'),
            )
        connection.commit()
    return MonitoredContact(
        contact_id=contact_id,
        workspace_id='ws-1',
        actor_telegram_id=111,
        name='Tech Company s.r.o.',
        ico='87654321',
        dic='2020202020',
        ic_dph='SK2020202020',
        address='Old address',
        updated_at='2026-08-01T10:00:00+00:00',
    )


def _details(*, dic: str | None = '2020202020') -> RegistryCompanyDetails:
    return RegistryCompanyDetails(
        subject_id='42',
        name='Tech Company s.r.o.',
        ico='87654321',
        dic=dic,
        ic_dph=None,
        address='New legal address',
        city='Bratislava',
        is_active=True,
        provider_sources=('slovak_rpo',),
    )


def test_next_monitor_slot_is_calendar_based_and_dst_aware() -> None:
    assert next_monitor_slot(
        now=NOW,
        timezone_name='Europe/Bratislava',
        anchor='2026-08-03T03:00:00',
        interval_days=14,
    ) == datetime(2026, 8, 17, 1, 0, tzinfo=timezone.utc)
    assert next_monitor_slot(
        now=datetime(2026, 10, 26, 2, 0, tzinfo=timezone.utc),
        timezone_name='Europe/Bratislava',
        anchor='2026-08-03T03:00:00',
        interval_days=14,
    ).astimezone(__import__('zoneinfo').ZoneInfo('Europe/Bratislava')).hour == 3


def test_missing_tax_values_do_not_clear_saved_values(tmp_path: Path) -> None:
    config = _config(tmp_path)
    contact = _seed(config)
    service = ContactRegistryMonitorService(config.db_path, config)
    context = __import__(
        'bot.services.workspace_context', fromlist=['WorkspaceContextService']
    ).WorkspaceContextService(config.db_path).resolve_for_background_workspace('ws-1')

    proposal = service.create_proposal(
        context, contact, now=NOW, details=_details(dic=None)
    )

    assert proposal is not None
    assert proposal.changed_fields == ('address',)
    assert proposal.new_values['dic'] == '2020202020'
    assert proposal.new_values['ic_dph'] == 'SK2020202020'


def test_approval_updates_contact_but_not_invoice_or_pdf(tmp_path: Path) -> None:
    config = _config(tmp_path)
    pdf_path = tmp_path / 'invoice.pdf'
    pdf_path.write_bytes(b'issued-pdf')
    contact = _seed(config, pdf_path=pdf_path)
    service = ContactRegistryMonitorService(config.db_path, config)
    context = __import__(
        'bot.services.workspace_context', fromlist=['WorkspaceContextService']
    ).WorkspaceContextService(config.db_path).resolve_for_background_workspace('ws-1')
    proposal = service.create_proposal(context, contact, now=NOW, details=_details())
    assert proposal is not None
    with sqlite3.connect(config.db_path) as connection:
        invoice_before = connection.execute('SELECT * FROM invoice').fetchone()
    pdf_before = pdf_path.read_bytes()

    result = service.resolve(
        proposal_id=proposal.proposal_id,
        actor_telegram_id=111,
        decision='yes',
        now=datetime(2026, 8, 3, 1, 5, tzinfo=timezone.utc),
    )

    assert result.status == 'applied'
    with sqlite3.connect(config.db_path) as connection:
        address = connection.execute(
            'SELECT address FROM contact WHERE id=?', (contact.contact_id,)
        ).fetchone()[0]
        invoice_after = connection.execute('SELECT * FROM invoice').fetchone()
    assert address == 'New legal address'
    assert invoice_after == invoice_before
    assert pdf_path.read_bytes() == pdf_before
    assert service.resolve(
        proposal_id=proposal.proposal_id,
        actor_telegram_id=111,
        decision='yes',
        now=datetime(2026, 8, 3, 1, 6, tzinfo=timezone.utc),
    ).status == 'stale'


def test_each_pending_proposal_is_independently_actionable(tmp_path: Path) -> None:
    config = _config(tmp_path)
    contact = _seed(config)
    service = ContactRegistryMonitorService(config.db_path, config)
    context = __import__(
        'bot.services.workspace_context', fromlist=['WorkspaceContextService']
    ).WorkspaceContextService(config.db_path).resolve_for_background_workspace('ws-1')
    first = service.create_proposal(context, contact, now=NOW, details=_details())
    assert first is not None

    with sqlite3.connect(config.db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO contact (workspace_id, supplier_telegram_id, name, ico, dic, "
            "ic_dph, address, email, source_type, updated_at) VALUES "
            "('ws-1', 111, 'MPBAU', '12344321', '2020202020', 'SK2020202020', "
            "'Old address', 'contact@example.test', 'manual', ?)",
            ('2026-08-01T10:00:00+00:00',),
        )
        second_contact_id = int(cursor.lastrowid)
        connection.commit()
    second_contact = MonitoredContact(
        contact_id=second_contact_id,
        workspace_id='ws-1',
        actor_telegram_id=111,
        name='MPBAU',
        ico='12344321',
        dic='2020202020',
        ic_dph='SK2020202020',
        address='Old address',
        updated_at='2026-08-01T10:00:00+00:00',
    )
    second_details = RegistryCompanyDetails(
        subject_id='43', name='MPBAU s. r. o.', ico='12344321',
        dic='2020202020', ic_dph=None, address='New legal address',
        city='Bratislava', is_active=True, provider_sources=('slovak_rpo',),
    )
    second = service.create_proposal(context, second_contact, now=NOW, details=second_details)
    assert second is not None and second.proposal_id != first.proposal_id

    assert service.resolve(
        proposal_id=first.proposal_id, actor_telegram_id=111, decision='yes', now=NOW,
    ).status == 'applied'
    assert service.resolve(
        proposal_id=second.proposal_id, actor_telegram_id=111, decision='yes', now=NOW,
    ).status == 'applied'


def test_due_contacts_include_a_nonselected_active_profile(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = _seed(config)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            "INSERT INTO workspace "
            "(workspace_id, display_name, storage_key, drive_folder_name, status, created_at, updated_at) "
            "VALUES ('ws-2', 'Other profile', 'ws-2', 'Other profile', 'active', ?, ?)",
            ('2026-08-01T00:00:00+00:00', '2026-08-01T00:00:00+00:00'),
        )
        connection.execute(
            "INSERT INTO workspace_membership "
            "(workspace_id, telegram_id, role, status, created_at, updated_at) "
            "VALUES ('ws-2', 111, 'owner', 'active', ?, ?)",
            ('2026-08-01T00:00:00+00:00', '2026-08-01T00:00:00+00:00'),
        )
        connection.execute(
            "INSERT INTO supplier "
            "(workspace_id, telegram_id, name, ico, dic, address, iban, swift, email, days_due) "
            "VALUES ('ws-2', 111, 'Other supplier', '11112222', '1010101010', 'Old', "
            "'SK000', 'TEST', 'other@example.test', 14)"
        )
        cursor = connection.execute(
            "INSERT INTO contact "
            "(workspace_id, supplier_telegram_id, name, ico, dic, address, email, source_type, updated_at) "
            "VALUES ('ws-2', 111, 'Other profile contact', '12344321', '1010101010', "
            "'Old address', '', 'manual', '2026-08-01T10:00:00+00:00')"
        )
        second_id = int(cursor.lastrowid)
        connection.execute(
            "INSERT INTO active_workspace_selection (telegram_id, workspace_id, updated_at) "
            "VALUES (111, 'ws-1', '2026-08-01T00:00:00+00:00')"
        )
        connection.commit()

    due = ContactRegistryMonitorService(config.db_path, config).list_due_contacts(
        now=NOW, include_not_due=True,
    )

    assert {row.contact_id for row in due} == {first.contact_id, second_id}


def test_wrong_actor_and_changed_contact_fail_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    contact = _seed(config)
    service = ContactRegistryMonitorService(config.db_path, config)
    context = __import__(
        'bot.services.workspace_context', fromlist=['WorkspaceContextService']
    ).WorkspaceContextService(config.db_path).resolve_for_background_workspace('ws-1')
    proposal = service.create_proposal(context, contact, now=NOW, details=_details())
    assert proposal is not None
    assert service.resolve(
        proposal_id=proposal.proposal_id,
        actor_telegram_id=999,
        decision='yes',
        now=NOW,
    ).status == 'forbidden'
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            "UPDATE contact SET address='Manual correction', updated_at=? WHERE id=?",
            ('2026-08-03T01:01:00+00:00', contact.contact_id),
        )
        connection.commit()
    assert service.resolve(
        proposal_id=proposal.proposal_id,
        actor_telegram_id=111,
        decision='yes',
        now=datetime(2026, 8, 3, 1, 2, tzinfo=timezone.utc),
    ).status == 'stale'


def test_expired_proposal_is_never_applied_and_remains_expired_on_replay(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    contact = _seed(config)
    service = ContactRegistryMonitorService(config.db_path, config)
    context = __import__(
        'bot.services.workspace_context', fromlist=['WorkspaceContextService']
    ).WorkspaceContextService(config.db_path).resolve_for_background_workspace('ws-1')
    proposal = service.create_proposal(context, contact, now=NOW, details=_details())
    assert proposal is not None
    after_expiry = datetime(2026, 9, 3, 1, 0, tzinfo=timezone.utc)

    first = service.resolve(
        proposal_id=proposal.proposal_id,
        actor_telegram_id=111,
        decision='yes',
        now=after_expiry,
    )
    replay = service.resolve(
        proposal_id=proposal.proposal_id,
        actor_telegram_id=111,
        decision='yes',
        now=after_expiry,
    )

    assert first.status == 'expired'
    assert replay.status == 'expired'
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            'SELECT address FROM contact WHERE id=?', (contact.contact_id,)
        ).fetchone()[0] == 'Old address'


def test_identity_conflict_is_distinct_from_stale_and_writes_nothing(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    contact = _seed(config)
    service = ContactRegistryMonitorService(config.db_path, config)
    context = __import__(
        'bot.services.workspace_context', fromlist=['WorkspaceContextService']
    ).WorkspaceContextService(config.db_path).resolve_for_background_workspace('ws-1')
    details = RegistryCompanyDetails(
        subject_id='42',
        name='Official collision s.r.o.',
        ico=contact.ico,
        dic=contact.dic,
        ic_dph=contact.ic_dph,
        address='New legal address',
        city='Bratislava',
        is_active=True,
        provider_sources=('slovak_rpo',),
    )
    proposal = service.create_proposal(context, contact, now=NOW, details=details)
    assert proposal is not None
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            "INSERT INTO contact "
            "(workspace_id, supplier_telegram_id, name, ico, dic, address, email, "
            "source_type, updated_at) VALUES "
            "('ws-1', 111, 'Official collision s.r.o.', '11223344', '2020202021', "
            "'Other address', '', 'manual', ?)",
            ('2026-08-03T01:01:00+00:00',),
        )
        connection.commit()

    result = service.resolve(
        proposal_id=proposal.proposal_id,
        actor_telegram_id=111,
        decision='yes',
        now=NOW,
    )

    assert result.status == 'conflict'
    assert result.reason == 'contact_identity_conflict'
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            'SELECT name, address FROM contact WHERE id=?', (contact.contact_id,)
        ).fetchone() == ('Tech Company s.r.o.', 'Old address')


def test_inactive_owner_profile_is_monitored_without_reactivation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    contact = _seed(config)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("UPDATE workspace SET status='inactive' WHERE workspace_id='ws-1'")
        connection.execute("UPDATE workspace_membership SET status='inactive' WHERE workspace_id='ws-1'")
        connection.commit()

    result = asyncio.run(send_contact_registry_monitor_once(
        bot=None, config=config, now=NOW, persist=True,
        search_provider=_Search(), details_provider=_Details(),
    ))

    assert result.proposals_created == 1
    service = ContactRegistryMonitorService(config.db_path, config)
    assert service.resolve(
        proposal_id=sqlite3.connect(config.db_path).execute(
            'SELECT proposal_id FROM contact_registry_change_proposal'
        ).fetchone()[0],
        actor_telegram_id=111, decision='yes', now=NOW,
    ).status == 'applied'
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            'SELECT status FROM workspace WHERE workspace_id=?', ('ws-1',)
        ).fetchone()[0] == 'inactive'
        assert connection.execute(
            'SELECT address FROM contact WHERE id=?', (contact.contact_id,)
        ).fetchone()[0] == 'New legal address'


def test_inactive_profile_is_excluded_when_owner_authorization_is_not_active(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    contact = _seed(config)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute("UPDATE workspace SET status='inactive' WHERE workspace_id='ws-1'")
        connection.execute(
            "UPDATE workspace_membership SET status='inactive' WHERE workspace_id='ws-1'"
        )
        connection.execute(
            "UPDATE authorized_users SET status='blocked' WHERE telegram_id=111"
        )
        connection.commit()

    due = ContactRegistryMonitorService(config.db_path, config).list_due_contacts(
        now=NOW, include_not_due=True,
    )

    assert due == []
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            'SELECT address FROM contact WHERE id=?', (contact.contact_id,)
        ).fetchone()[0] == 'Old address'


class _Search:
    def __init__(self) -> None:
        self.only_active: bool | None = None

    async def search(self, query: str, *, only_active: bool = True):
        self.only_active = only_active
        return [
            RegistryCompanyCandidate(
                subject_id='42',
                name='Tech Company s.r.o.',
                ico=query,
                city='Bratislava',
                short_address='New legal address',
                is_active=True,
                provider='slovak_rpo',
            )
        ]


class _Details:
    async def get_details(self, subject_id: str):
        return _details()


def test_read_only_dry_run_detects_change_without_writes(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _seed(config)
    search = _Search()

    result = asyncio.run(
        send_contact_registry_monitor_once(
            bot=None,
            config=config,
            now=NOW,
            persist=False,
            search_provider=search,
            details_provider=_Details(),
        )
    )

    assert result.checked_contacts == 1
    assert result.proposals_created == 1
    assert search.only_active is False
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            'SELECT count(*) FROM contact_registry_change_proposal'
        ).fetchone()[0] == 0
        assert connection.execute(
            'SELECT count(*) FROM contact_registry_monitor_state'
        ).fetchone()[0] == 0


def test_callback_payload_is_bounded() -> None:
    keyboard = proposal_keyboard('00000000-0000-4000-8000-000000000000')
    for button in keyboard.inline_keyboard[0]:
        assert button.callback_data is not None
        assert len(button.callback_data.encode('utf-8')) <= 64


def test_notification_identifies_contact_and_ico_for_multiple_cards() -> None:
    proposal = ContactRegistryChangeProposal(
        proposal_id='00000000-0000-4000-8000-000000000000',
        workspace_id='ws-1',
        actor_telegram_id=111,
        contact_id=1,
        contact_updated_at='2026-08-01T10:00:00+00:00',
        ico='87654321',
        old_values={
            'name': 'Tech Company s.r.o.',
            'address': 'Old address',
            'dic': '2020202020',
            'ic_dph': None,
        },
        new_values={
            'name': 'Tech Company s.r.o.',
            'address': 'New address',
            'dic': '2020202020',
            'ic_dph': None,
        },
        changed_fields=('address',),
        provider_sources=('slovak_rpo',),
        status='pending',
        expires_at=datetime(2026, 9, 2, 1, 0, tzinfo=timezone.utc),
    )

    text = format_change_notification(proposal)

    assert 'Kontakt: Tech Company s.r.o.' in text
    assert 'IČO: 87654321' in text


def test_dry_run_can_audit_before_first_schedule_without_persistence(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _seed(config)
    result = asyncio.run(
        send_contact_registry_monitor_once(
            bot=None,
            config=config,
            now=datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc),
            persist=False,
            include_not_due=True,
            search_provider=_Search(),
            details_provider=_Details(),
        )
    )
    assert result.eligible_contacts == 1
    assert result.proposals_created == 1
    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute(
            'SELECT count(*) FROM contact_registry_change_proposal'
        ).fetchone()[0] == 0
