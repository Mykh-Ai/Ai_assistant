from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.access_admin import cmd_customization_requests
from bot.services import product_truth
from bot.services.access_control import AccessControlService, ROLE_ADMIN
from bot.services.authorization import TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.customization_requests import (
    STATUS_CANCELLED_BY_USER,
    STATUS_CONFIRMED_PENDING_REVIEW,
    STATUS_CONVERTED_TO_BACKLOG,
    STATUS_EXPIRED_UNCONFIRMED,
    STATUS_REVIEWED_REJECTED,
    CustomizationRequestService,
)
from bot.services.db import init_db


ADMIN_ID = 960001
USER_ID = 960002
OTHER_USER_ID = 960003
UNKNOWN_ID = 960004


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str, user_id: int) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


class _DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.sent.append((telegram_id, text))


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'customization-admin.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset(),
        admin_telegram_user_ids=frozenset({ADMIN_ID}),
    )


def _create_request(
    service: CustomizationRequestService,
    *,
    request_id: str,
    telegram_id: int = USER_ID,
    title: str = 'Mesa\u010dn\u00fd report',
    summary: str = 'Pou\u017e\u00edvate\u013e chce mesa\u010dn\u00fd report tr\u017eieb.',
    status: str = STATUS_CONFIRMED_PENDING_REVIEW,
    raw_text_hash: str = 'hash-value-not-for-ui',
) -> None:
    service.create_confirmed_customization_request(
        request_id=request_id,
        telegram_id=telegram_id,
        supplier_telegram_id=telegram_id,
        workspace_id=f'telegram:{telegram_id}',
        source_channel='text',
        source_triage_class='customization_request_candidate',
        source_capability_id='monthly_report' if status == STATUS_CONFIRMED_PENDING_REVIEW else None,
        source_topic_id='customization_request',
        normalized_title=title,
        normalized_summary=summary,
        redacted_original_text=summary,
        raw_text_hash=raw_text_hash,
        status=status,
    )


def test_admin_can_list_pending_customization_requests(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_admin_pending_1', telegram_id=USER_ID)

    message = _DummyMessage('/customization_requests', ADMIN_ID)
    asyncio.run(cmd_customization_requests(message, config))

    output = message.answers[-1]
    assert 'Po\u017eiadavky \u010dakaj\u00face na kontrolu:' in output
    assert 'telegram_id=960002' in output
    assert 'workspace_id=telegram:960002' in output
    assert 'trieda=customization_request_candidate' in output
    assert 'n\u00e1zov=Mesa\u010dn\u00fd report' in output
    assert 'status=confirmed_pending_review' in output
    assert 'capability_id=monthly_report' in output


def test_admin_sees_empty_state_when_no_pending_requests(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_requests', ADMIN_ID)

    asyncio.run(cmd_customization_requests(message, config))

    assert message.answers == ['Moment\u00e1lne nie s\u00fa \u017eiadne po\u017eiadavky \u010dakaj\u00face na kontrolu.']


def test_non_admin_authorized_user_cannot_list_customization_requests(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    _create_request(CustomizationRequestService(config.db_path), request_id='cr_hidden_from_user')
    message = _DummyMessage('/customization_requests', USER_ID)

    asyncio.run(cmd_customization_requests(message, config))

    assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_unauthorized_user_is_blocked_by_middleware_for_customization_requests(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_requests', UNKNOWN_ID)
    state = _DummyState()
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(
        TelegramUserAuthorizationMiddleware()(
            _handler,
            message,
            {'config': config, 'state': state},
        )
    )

    assert calls == []
    assert state.cleared is True
    assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_bootstrap_admin_command_passes_middleware_without_user_access(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_requests', ADMIN_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    assert calls == ['handler-called']
    assert message.answers == []


def test_customization_request_admin_list_only_includes_pending_requests(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_pending_visible', title='Pending visible')
    for status in (
        STATUS_REVIEWED_REJECTED,
        STATUS_CONVERTED_TO_BACKLOG,
        STATUS_CANCELLED_BY_USER,
        STATUS_EXPIRED_UNCONFIRMED,
    ):
        _create_request(
            service,
            request_id=f'cr_hidden_{status}',
            title=f'Hidden {status}',
            status=status,
        )
    message = _DummyMessage('/customization_requests', ADMIN_ID)

    asyncio.run(cmd_customization_requests(message, config))

    output = message.answers[-1]
    assert 'Pending visible' in output
    assert 'Hidden reviewed_rejected' not in output
    assert 'Hidden converted_to_backlog' not in output
    assert 'Hidden cancelled_by_user' not in output
    assert 'Hidden expired_unconfirmed' not in output


def test_customization_request_admin_output_omits_hash_and_redacts_sensitive_values(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(
        service,
        request_id='cr_sensitive',
        title='Report for person@example.com token sk-secretTOKEN123',
        summary='Send report to person@example.com phone +421 900 123 456 IBAN SK7700000000000000000000',
        raw_text_hash='raw-hash-should-not-render',
    )
    message = _DummyMessage('/customization_requests', ADMIN_ID)

    asyncio.run(cmd_customization_requests(message, config))

    output = message.answers[-1]
    assert 'raw-hash-should-not-render' not in output
    assert 'person@example.com' not in output
    assert 'sk-secretTOKEN123' not in output
    assert '+421 900 123 456' not in output
    assert 'SK7700000000000000000000' not in output
    assert '[REDACTED]' in output


def test_admin_list_is_admin_wide_but_not_user_visible(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_user_one', telegram_id=USER_ID, title='User one')
    _create_request(service, request_id='cr_user_two', telegram_id=OTHER_USER_ID, title='User two')
    admin_message = _DummyMessage('/customization_requests', ADMIN_ID)
    user_message = _DummyMessage('/customization_requests', USER_ID)

    asyncio.run(cmd_customization_requests(admin_message, config))
    asyncio.run(cmd_customization_requests(user_message, config))

    assert 'telegram_id=960002' in admin_message.answers[-1]
    assert 'telegram_id=960003' in admin_message.answers[-1]
    assert user_message.answers == [UNAUTHORIZED_MESSAGE]


def test_customization_request_admin_command_is_read_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    access_service = AccessControlService(config.db_path)
    access_service.approve_user(telegram_id=ADMIN_ID, approved_by=ADMIN_ID, role=ROLE_ADMIN)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_read_only', telegram_id=USER_ID)
    before_product_truth = [entry.to_payload() for entry in product_truth.list_capabilities()]
    bot = _DummyBot()
    message = _DummyMessage('/customization_requests', ADMIN_ID)

    asyncio.run(cmd_customization_requests(message, config))

    after = service.get_customization_request_for_user(
        request_id='cr_read_only',
        telegram_id=USER_ID,
    )
    assert after is not None
    assert after.status == STATUS_CONFIRMED_PENDING_REVIEW
    assert [entry.to_payload() for entry in product_truth.list_capabilities()] == before_product_truth
    assert bot.sent == []
    assert not hasattr(service, 'notify_admin')
    assert not hasattr(service, 'send_admin_notification')
    assert not hasattr(service, 'create_code_agent_handoff')


def test_customization_request_admin_limit_uses_newest_first(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    for index in range(12):
        _create_request(
            service,
            request_id=f'cr_limit_{index:02d}',
            title=f'Request {index:02d}',
        )
    message = _DummyMessage('/customization_requests', ADMIN_ID)

    asyncio.run(cmd_customization_requests(message, config))

    output = message.answers[-1]
    assert 'Request 11' in output
    assert 'Request 02' in output
    assert 'Request 01' not in output
    assert 'Request 00' not in output
