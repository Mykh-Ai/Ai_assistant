from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from bot.config import Config
from bot.handlers import contact_registry_monitor as handler
from bot.services.contact_registry_monitor import (
    ContactRegistryMonitorService,
    MonitoredContact,
    ProposalResolution,
)
from bot.services.db import init_db
from bot.services.decision_resolver import resolve_yes_no
from bot.services.slovak_company_registry import RegistryCompanyDetails
from bot.services.workspace_context import WorkspaceContextService


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='test',
        openai_api_key=None,
        openai_stt_model='gpt-test',
        openai_llm_model='gpt-test',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path / 'storage',
    )


class _Message:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.cleared = False

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def edit_reply_markup(self, *, reply_markup) -> None:
        self.cleared = reply_markup is None


class _Callback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.from_user = type('User', (), {'id': 111})()
        self.message = _Message()
        self.callback_answers: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, *, show_alert: bool = False) -> None:
        self.callback_answers.append((text, show_alert))


def test_monitor_context_uses_shared_yes_no_resolver_without_llm() -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='contact_registry_monitor_proposal',
            user_input_text='yes',
            api_key=None,
            model='gpt-test',
        )
    ) == 'yes'
    assert asyncio.run(
        resolve_yes_no(
            context_name='contact_registry_monitor_proposal',
            user_input_text='no',
            api_key=None,
            model='gpt-test',
        )
    ) == 'no'


def test_callback_dispatches_shared_resolver_result(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, str] = {}

    async def fake_resolver(**kwargs):
        seen['context'] = kwargs['context_name']
        seen['input'] = kwargs['user_input_text']
        return 'yes'

    class _Service:
        def __init__(self, db_path, config) -> None:
            pass

        def resolve(self, **kwargs):
            seen['decision'] = kwargs['decision']
            return ProposalResolution('applied', 'Tech Company s.r.o.')

    monkeypatch.setattr(handler, 'resolve_yes_no', fake_resolver)
    monkeypatch.setattr(handler, 'ContactRegistryMonitorService', _Service)
    callback = _Callback(
        'contact_monitor:yes:00000000-0000-4000-8000-000000000000'
    )

    asyncio.run(
        handler.contact_registry_monitor_callback(callback, _config(tmp_path))
    )

    assert seen == {
        'context': 'contact_registry_monitor_proposal',
        'input': 'yes',
        'decision': 'yes',
    }
    assert callback.message.cleared is True
    assert 'PDF' in callback.message.answers[0]


def test_two_distinct_proposal_buttons_remain_independently_actionable(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    now_text = now.isoformat()
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            "INSERT INTO authorized_users "
            "(telegram_id, role, status, created_at) VALUES (111, 'user', 'active', ?)",
            (now_text,),
        )
        connection.execute(
            "INSERT INTO workspace "
            "(workspace_id, display_name, storage_key, drive_folder_name, status, "
            "created_at, updated_at) VALUES "
            "('ws-1', 'Test', 'ws-1', 'Test', 'active', ?, ?)",
            (now_text, now_text),
        )
        connection.execute(
            "INSERT INTO workspace_membership "
            "(workspace_id, telegram_id, role, status, created_at, updated_at) "
            "VALUES ('ws-1', 111, 'owner', 'active', ?, ?)",
            (now_text, now_text),
        )
        connection.execute(
            "INSERT INTO supplier "
            "(workspace_id, telegram_id, name, ico, dic, address, iban, swift, "
            "email, days_due) VALUES "
            "('ws-1', 111, 'Supplier', '12345678', '1234567890', 'Old', "
            "'SK000', 'TEST', 'a@example.test', 14)"
        )
        contact_ids = []
        for name, ico in (
            ('First contact', '87654321'),
            ('Second contact', '12344321'),
        ):
            cursor = connection.execute(
                "INSERT INTO contact "
                "(workspace_id, supplier_telegram_id, name, ico, dic, address, "
                "email, source_type, updated_at) VALUES "
                "('ws-1', 111, ?, ?, '2020202020', 'Old address', '', 'manual', ?)",
                (name, ico, now_text),
            )
            contact_ids.append(int(cursor.lastrowid))
        connection.commit()

    context = WorkspaceContextService(config.db_path).resolve_for_background_workspace('ws-1')
    service = ContactRegistryMonitorService(config.db_path, config)
    proposals = []
    for index, (contact_id, name, ico) in enumerate(
        zip(
            contact_ids,
            ('First contact', 'Second contact'),
            ('87654321', '12344321'),
        ),
        start=1,
    ):
        proposal = service.create_proposal(
            context,
            MonitoredContact(
                contact_id=contact_id,
                workspace_id='ws-1',
                actor_telegram_id=111,
                name=name,
                ico=ico,
                dic='2020202020',
                ic_dph=None,
                address='Old address',
                updated_at=now_text,
            ),
            now=now,
            details=RegistryCompanyDetails(
                subject_id=str(index),
                name=name,
                ico=ico,
                dic='2020202020',
                ic_dph=None,
                address=f'New address {index}',
                city='Bratislava',
                is_active=True,
                provider_sources=('slovak_rpo',),
            ),
        )
        assert proposal is not None
        proposals.append(proposal)

    callbacks = [
        _Callback(f'contact_monitor:yes:{proposal.proposal_id}')
        for proposal in proposals
    ]
    asyncio.run(handler.contact_registry_monitor_callback(callbacks[0], config))
    asyncio.run(handler.contact_registry_monitor_callback(callbacks[1], config))

    assert all(callback.message.cleared for callback in callbacks)
    assert all('aktualizovaný' in callback.message.answers[0] for callback in callbacks)
    with sqlite3.connect(config.db_path) as connection:
        addresses = connection.execute(
            'SELECT address FROM contact ORDER BY id'
        ).fetchall()
    assert addresses == [('New address 1',), ('New address 2',)]


def test_owned_stale_proposal_clears_markup_and_explains_no_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class _Service:
        def __init__(self, db_path, config) -> None:
            pass

        def resolve(self, **kwargs):
            return ProposalResolution('stale', reason='contact_version_changed')

    monkeypatch.setattr(handler, 'ContactRegistryMonitorService', _Service)
    callback = _Callback(
        'contact_monitor:yes:00000000-0000-4000-8000-000000000000'
    )

    asyncio.run(handler.contact_registry_monitor_callback(callback, _config(tmp_path)))

    assert callback.message.cleared is True
    assert 'Nič som nezmenil' in callback.message.answers[0]
    assert callback.callback_answers[-1] == (None, False)


def test_owned_conflict_proposal_is_not_reported_as_generic_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class _Service:
        def __init__(self, db_path, config) -> None:
            pass

        def resolve(self, **kwargs):
            return ProposalResolution('conflict', reason='contact_identity_conflict')

    monkeypatch.setattr(handler, 'ContactRegistryMonitorService', _Service)
    callback = _Callback(
        'contact_monitor:yes:00000000-0000-4000-8000-000000000000'
    )

    asyncio.run(handler.contact_registry_monitor_callback(callback, _config(tmp_path)))

    assert callback.message.cleared is True
    assert 'koliduje s iným kontaktom' in callback.message.answers[0]
    assert callback.callback_answers[-1] == (None, False)


def test_owned_expired_proposal_clears_markup_and_explains_expiry(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class _Service:
        def __init__(self, db_path, config) -> None:
            pass

        def resolve(self, **kwargs):
            return ProposalResolution('expired', reason='proposal_expired')

    monkeypatch.setattr(handler, 'ContactRegistryMonitorService', _Service)
    callback = _Callback(
        'contact_monitor:yes:00000000-0000-4000-8000-000000000000'
    )

    asyncio.run(handler.contact_registry_monitor_callback(callback, _config(tmp_path)))

    assert callback.message.cleared is True
    assert 'vypršala' in callback.message.answers[0]
    assert callback.callback_answers[-1] == (None, False)


def test_forbidden_proposal_retains_markup_when_ownership_is_unproven(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class _Service:
        def __init__(self, db_path, config) -> None:
            pass

        def resolve(self, **kwargs):
            return ProposalResolution('forbidden', reason='actor_mismatch')

    monkeypatch.setattr(handler, 'ContactRegistryMonitorService', _Service)
    callback = _Callback(
        'contact_monitor:yes:00000000-0000-4000-8000-000000000000'
    )

    asyncio.run(handler.contact_registry_monitor_callback(callback, _config(tmp_path)))

    assert callback.message.cleared is False
    assert callback.message.answers == []
    assert callback.callback_answers[-1][1] is True


def test_cleanup_failure_is_logged_without_reversing_applied_result(
    monkeypatch,
    tmp_path: Path,
    caplog,
) -> None:
    class _Service:
        def __init__(self, db_path, config) -> None:
            pass

        def resolve(self, **kwargs):
            return ProposalResolution('applied', 'Tech Company s.r.o.')

    class _BrokenMessage(_Message):
        async def edit_reply_markup(self, *, reply_markup) -> None:
            raise RuntimeError('telegram unavailable')

    monkeypatch.setattr(handler, 'ContactRegistryMonitorService', _Service)
    callback = _Callback(
        'contact_monitor:yes:00000000-0000-4000-8000-000000000000'
    )
    callback.message = _BrokenMessage()

    asyncio.run(handler.contact_registry_monitor_callback(callback, _config(tmp_path)))

    assert 'aktualizovaný' in callback.message.answers[0]
    assert 'keyboard cleanup failed' in caplog.text
