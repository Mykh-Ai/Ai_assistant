from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.access_admin import (
    access_requests_alias,
    cmd_access_requests,
    cmd_approve,
    cmd_block,
    cmd_reject,
    cmd_users,
    users_alias,
)
from bot.handlers.onboarding import cmd_onboarding
from bot.handlers.start import APPROVED_ACCESS_NEXT_STEP_MESSAGE, cmd_start
from bot.services.access_control import ACCESS_STATUS_APPROVED, ACCESS_STATUS_PENDING, ACCESS_STATUS_REJECTED
from bot.services.access_control import AUTHORIZED_STATUS_BLOCKED, AccessControlService
from bot.services.authorization import ACCESS_REQUEST_MESSAGE, TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.contact_service import ContactService
from bot.services.db import init_db, managed_connection
from bot.services.supplier_service import SupplierService


ADMIN_ID = 900001
UNKNOWN_ID = 900002
BOOTSTRAP_ID = 900003


class _DummyUser:
    def __init__(
        self,
        user_id: int,
        *,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> None:
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name


class _DummyMessage:
    def __init__(
        self,
        text: str,
        user_id: int,
        *,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> None:
        self.text = text
        self.from_user = _DummyUser(
            user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False
        self.current_state = None

    async def clear(self) -> None:
        self.cleared = True

    async def set_state(self, state) -> None:
        self.current_state = state


class _DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.sent.append((telegram_id, text))


class _FailingBot:
    async def send_message(self, telegram_id: int, text: str) -> None:
        raise RuntimeError('telegram unavailable')


def _config(
    tmp_path: Path,
    *,
    allowed: frozenset[int] = frozenset(),
    admins: frozenset[int] = frozenset({ADMIN_ID}),
) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'access.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=allowed,
        admin_telegram_user_ids=admins,
    )


def _invoice_count(db_path: Path) -> int:
    with managed_connection(db_path) as connection:
        row = connection.execute('SELECT COUNT(*) FROM invoice').fetchone()
    return int(row[0])


def test_unknown_start_creates_pending_access_request_only_and_does_not_call_handler(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage(
        '/start',
        UNKNOWN_ID,
        username='requester',
        first_name='Test',
        last_name='User',
    )
    state = _DummyState()
    bot = _DummyBot()
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    result = asyncio.run(
        TelegramUserAuthorizationMiddleware()(
            _handler,
            message,
            {'config': config, 'state': state, 'bot': bot},
        )
    )

    request = AccessControlService(config.db_path).get_access_request(UNKNOWN_ID)
    assert result is None
    assert calls == []
    assert state.cleared is True
    assert message.answers == [ACCESS_REQUEST_MESSAGE]
    assert request is not None
    assert request.status == ACCESS_STATUS_PENDING
    assert request.username == 'requester'
    assert SupplierService(config.db_path).get_by_telegram_id(UNKNOWN_ID) is None
    assert ContactService(config.db_path).get_all_by_supplier(UNKNOWN_ID) == []
    assert _invoice_count(config.db_path) == 0
    assert not (tmp_path / 'workspaces').exists()
    assert bot.sent and bot.sent[0][0] == ADMIN_ID
    assert 'telegram_id=900002' in bot.sent[0][1]


def test_admin_can_list_pending_access_requests(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).create_or_refresh_pending_request(
        request=_request(UNKNOWN_ID, username='requester')
    )
    message = _DummyMessage('/access_requests', ADMIN_ID)

    asyncio.run(cmd_access_requests(message, config))

    assert 'telegram_id=900002' in message.answers[-1]
    assert 'username=requester' in message.answers[-1]


def test_admin_text_aliases_can_list_users_and_access_requests(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = AccessControlService(config.db_path)
    service.create_or_refresh_pending_request(request=_request(UNKNOWN_ID, username='requester'))
    service.approve_user(telegram_id=BOOTSTRAP_ID, approved_by=ADMIN_ID)

    access_message = _DummyMessage('\u0437\u0430\u043f\u0438\u0442', ADMIN_ID)
    users_message = _DummyMessage('\u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456', ADMIN_ID)

    asyncio.run(access_requests_alias(access_message, config))
    asyncio.run(users_alias(users_message, config))

    assert 'telegram_id=900002' in access_message.answers[-1]
    assert 'telegram_id=900003' in users_message.answers[-1]


def test_admin_text_alias_passes_middleware_for_bootstrap_admin_without_allowed_access(tmp_path: Path) -> None:
    config = _config(tmp_path, admins=frozenset({ADMIN_ID}))
    init_db(config.db_path)
    message = _DummyMessage('\u0437\u0430\u043f\u0440\u043e\u0441', ADMIN_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    assert calls == ['handler-called']
    assert message.answers == []


def test_non_admin_cannot_list_or_decide_access(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)

    for handler, text in [
        (cmd_access_requests, '/access_requests'),
        (cmd_approve, f'/approve {UNKNOWN_ID}'),
        (cmd_reject, f'/reject {UNKNOWN_ID}'),
        (cmd_block, f'/block {UNKNOWN_ID}'),
        (cmd_users, '/users'),
    ]:
        message = _DummyMessage(text, UNKNOWN_ID)
        asyncio.run(handler(message, config))
        assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_admin_can_approve_pending_user_and_user_can_reach_supplier_onboarding(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).create_or_refresh_pending_request(
        request=_request(UNKNOWN_ID, username='requester')
    )
    admin_message = _DummyMessage(f'/approve {UNKNOWN_ID}', ADMIN_ID)
    bot = _DummyBot()

    asyncio.run(cmd_approve(admin_message, config, bot=bot))

    request = AccessControlService(config.db_path).get_access_request(UNKNOWN_ID)
    user = AccessControlService(config.db_path).get_authorized_user(UNKNOWN_ID)
    assert request is not None and request.status == ACCESS_STATUS_APPROVED
    assert user is not None and user.status == 'active'
    assert bot.sent == [(UNKNOWN_ID, APPROVED_ACCESS_NEXT_STEP_MESSAGE)]
    assert '/supplier' in admin_message.answers[-1]

    supplier_message = _DummyMessage('/supplier', UNKNOWN_ID)
    state = _DummyState()
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')
        await cmd_onboarding(event, data['state'], data['config'])

    asyncio.run(
        TelegramUserAuthorizationMiddleware()(
            _handler,
            supplier_message,
            {'config': config, 'state': state},
        )
    )

    assert calls == ['handler-called']
    assert state.current_state is not None
    assert supplier_message.answers[-1].startswith('1/9')
    assert SupplierService(config.db_path).get_by_telegram_id(UNKNOWN_ID) is None


def test_approved_user_start_without_supplier_profile_gets_supplier_next_step(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=UNKNOWN_ID, approved_by=ADMIN_ID)
    message = _DummyMessage('/start', UNKNOWN_ID)

    asyncio.run(cmd_start(message, config))

    assert message.answers == [APPROVED_ACCESS_NEXT_STEP_MESSAGE]
    assert '/supplier' in message.answers[-1]
    assert SupplierService(config.db_path).get_by_telegram_id(UNKNOWN_ID) is None


def test_approve_keeps_user_active_when_approval_notification_fails(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).create_or_refresh_pending_request(
        request=_request(UNKNOWN_ID, username='requester')
    )
    admin_message = _DummyMessage(f'/approve {UNKNOWN_ID}', ADMIN_ID)

    asyncio.run(cmd_approve(admin_message, config, bot=_FailingBot()))

    user = AccessControlService(config.db_path).get_authorized_user(UNKNOWN_ID)
    assert user is not None and user.status == 'active'
    assert 'nepodarilo odoslat' in admin_message.answers[-1]
    assert '/supplier' in admin_message.answers[-1]


def test_rejected_user_remains_unauthorized_on_future_start(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).create_or_refresh_pending_request(
        request=_request(UNKNOWN_ID)
    )
    asyncio.run(cmd_reject(_DummyMessage(f'/reject {UNKNOWN_ID}', ADMIN_ID), config))

    message = _DummyMessage('/start', UNKNOWN_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    request = AccessControlService(config.db_path).get_access_request(UNKNOWN_ID)
    assert request is not None and request.status == ACCESS_STATUS_REJECTED
    assert calls == []
    assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_blocked_user_loses_access_without_data_deletion(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = AccessControlService(config.db_path)
    service.approve_user(telegram_id=UNKNOWN_ID, approved_by=ADMIN_ID)
    asyncio.run(cmd_block(_DummyMessage(f'/block {UNKNOWN_ID}', ADMIN_ID), config))

    message = _DummyMessage('/supplier', UNKNOWN_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    user = service.get_authorized_user(UNKNOWN_ID)
    assert user is not None and user.status == AUTHORIZED_STATUS_BLOCKED
    assert calls == []
    assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_allowed_telegram_user_ids_still_work_as_bootstrap_allowlist(tmp_path: Path) -> None:
    config = _config(tmp_path, allowed=frozenset({BOOTSTRAP_ID}))
    init_db(config.db_path)
    message = _DummyMessage('/supplier', BOOTSTRAP_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    assert calls == ['handler-called']
    assert message.answers == []


def _request(telegram_id: int, username: str | None = None):
    from bot.services.access_control import AccessRequestInput

    return AccessRequestInput(
        telegram_id=telegram_id,
        username=username,
        first_name='Test',
        last_name='User',
    )
