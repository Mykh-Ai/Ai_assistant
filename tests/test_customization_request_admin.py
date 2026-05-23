from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.access_admin import (
    CustomizationRequestAdminResponseStates,
    cmd_customization_request_accept,
    cmd_customization_request_detail,
    cmd_customization_request_reject,
    cmd_customization_request_reply,
    cmd_customization_requests,
    customization_request_response_preview_decision,
    customization_request_response_text,
)
from bot.services import product_truth
from bot.services.access_control import AccessControlService, ROLE_ADMIN
from bot.services.authorization import TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.customization_requests import (
    RESPONSE_DELIVERY_FAILED,
    RESPONSE_DELIVERY_PENDING,
    RESPONSE_DELIVERY_SUCCEEDED,
    RESPONSE_KIND_ANSWER,
    STATUS_CANCELLED_BY_USER,
    STATUS_CONFIRMED_PENDING_REVIEW,
    STATUS_CONVERTED_TO_BACKLOG,
    STATUS_EXPIRED_UNCONFIRMED,
    STATUS_REVIEWED_ACCEPTED,
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
    def __init__(self, data: dict | None = None, current_state: str | None = None) -> None:
        self.cleared = False
        self.data = dict(data or {})
        self.current_state = current_state

    async def clear(self) -> None:
        self.cleared = True
        self.current_state = None
        self.data.clear()

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return dict(self.data)

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, 'state') else state

    async def get_state(self) -> str | None:
        return self.current_state


class _DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.sent.append((telegram_id, text))


class _FailingBot:
    def __init__(self) -> None:
        self.attempts = 0

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.attempts += 1
        raise RuntimeError('telegram stack trace must not be persisted')


class _InspectingBot(_DummyBot):
    def __init__(self, service: CustomizationRequestService, request_id: str) -> None:
        super().__init__()
        self.service = service
        self.request_id = request_id
        self.record_before_send = None

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.record_before_send = self.service.get_customization_request_by_id_for_admin(
            request_id=self.request_id
        )
        await super().send_message(telegram_id, text)


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
    privacy_redaction_flags: str | None = None,
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
        privacy_redaction_flags=privacy_redaction_flags,
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


def test_admin_can_view_customization_request_detail_by_full_id(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(
        service,
        request_id='cr_detail_full_1234567890abcdef',
        telegram_id=USER_ID,
        privacy_redaction_flags='email,phone',
    )
    message = _DummyMessage('/customization_request cr_detail_full_1234567890abcdef', ADMIN_ID)

    asyncio.run(cmd_customization_request_detail(message, config))

    output = message.answers[-1]
    assert 'Detail po\u017eiadavky:' in output
    assert 'request_id=cr_detail_full_1234567890abcdef' in output
    assert 'status=confirmed_pending_review' in output
    assert 'confirmed_at=' in output
    assert 'telegram_id=960002' in output
    assert 'workspace_id=telegram:960002' in output
    assert 'source_channel=text' in output
    assert 'source_triage_class=customization_request_candidate' in output
    assert 'source_capability_id=monthly_report' in output
    assert 'source_topic_id=customization_request' in output
    assert 'privacy_redaction_flags=email,phone' in output
    assert 'n\u00e1zov=Mesa\u010dn\u00fd report' in output
    assert 'zhrnutie=Pou\u017e\u00edvate\u013e chce mesa\u010dn\u00fd report tr\u017eieb.' in output
    assert 'redacted_original_text=Pou\u017e\u00edvate\u013e chce mesa\u010dn\u00fd report tr\u017eieb.' in output


def test_admin_can_view_customization_request_detail_by_unique_prefix(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_unique_prefix_abcdef123456', title='Unique prefix title')
    message = _DummyMessage('/customization_request cr_unique_prefix', ADMIN_ID)

    asyncio.run(cmd_customization_request_detail(message, config))

    output = message.answers[-1]
    assert 'request_id=cr_unique_prefix_abcdef123456' in output
    assert 'n\u00e1zov=Unique prefix title' in output


def test_customization_request_detail_ambiguous_prefix_is_rejected(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_ambiguous_one_111111', title='First hidden')
    _create_request(service, request_id='cr_ambiguous_two_222222', title='Second hidden')
    message = _DummyMessage('/customization_request cr_ambiguous', ADMIN_ID)

    asyncio.run(cmd_customization_request_detail(message, config))

    output = message.answers[-1]
    assert output == 'Na\u0161iel som viac po\u017eiadaviek s t\u00fdmto za\u010diatkom ID. Pou\u017eite dlh\u0161\u00ed request_id.'
    assert 'First hidden' not in output
    assert 'Second hidden' not in output


def test_customization_request_detail_missing_and_short_prefix_are_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    short_message = _DummyMessage('/customization_request cr_x', ADMIN_ID)
    missing_message = _DummyMessage('/customization_request cr_missing_long_prefix', ADMIN_ID)

    asyncio.run(cmd_customization_request_detail(short_message, config))
    asyncio.run(cmd_customization_request_detail(missing_message, config))

    assert short_message.answers == [
        'Po\u017eiadavku som nena\u0161iel. Zadajte cel\u00fd request_id alebo aspo\u0148 8 znakov za\u010diatku ID.'
    ]
    assert missing_message.answers == ['Po\u017eiadavku som nena\u0161iel.']


def test_customization_request_detail_requires_request_id_argument(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_request', ADMIN_ID)

    asyncio.run(cmd_customization_request_detail(message, config))

    assert message.answers == ['Pou\u017eitie: /customization_request <request_id>']


def test_non_admin_authorized_user_cannot_view_customization_request_detail(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    _create_request(CustomizationRequestService(config.db_path), request_id='cr_detail_hidden_from_user')
    message = _DummyMessage('/customization_request cr_detail_hidden_from_user', USER_ID)

    asyncio.run(cmd_customization_request_detail(message, config))

    assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_unauthorized_user_is_blocked_by_middleware_for_customization_request_detail(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_request cr_detail_hidden', UNKNOWN_ID)
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


def test_bootstrap_admin_detail_command_passes_middleware_without_user_access(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_request cr_detail', ADMIN_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    assert calls == ['handler-called']
    assert message.answers == []


def test_customization_request_detail_omits_hash_and_redacts_sensitive_values(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(
        service,
        request_id='cr_detail_sensitive',
        title='Report for person@example.com token sk-secretTOKEN123',
        summary='Send report to person@example.com phone +421 900 123 456 IBAN SK7700000000000000000000',
        raw_text_hash='detail-raw-hash-should-not-render',
        privacy_redaction_flags='email,phone,iban,token',
    )
    message = _DummyMessage('/customization_request cr_detail_sensitive', ADMIN_ID)

    asyncio.run(cmd_customization_request_detail(message, config))

    output = message.answers[-1]
    assert 'raw_text_hash' not in output
    assert 'detail-raw-hash-should-not-render' not in output
    assert 'person@example.com' not in output
    assert 'sk-secretTOKEN123' not in output
    assert '+421 900 123 456' not in output
    assert 'SK7700000000000000000000' not in output
    assert '[REDACTED]' in output


def test_customization_request_detail_command_is_read_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_detail_read_only', telegram_id=USER_ID)
    before_product_truth = [entry.to_payload() for entry in product_truth.list_capabilities()]
    bot = _DummyBot()
    message = _DummyMessage('/customization_request cr_detail_read_only', ADMIN_ID)

    asyncio.run(cmd_customization_request_detail(message, config))

    after = service.get_customization_request_for_user(
        request_id='cr_detail_read_only',
        telegram_id=USER_ID,
    )
    assert after is not None
    assert after.status == STATUS_CONFIRMED_PENDING_REVIEW
    assert [entry.to_payload() for entry in product_truth.list_capabilities()] == before_product_truth
    assert bot.sent == []
    assert not hasattr(service, 'notify_admin')
    assert not hasattr(service, 'send_admin_notification')
    assert not hasattr(service, 'create_code_agent_handoff')


def test_admin_reply_command_is_admin_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_denied')
    state = _DummyState()
    message = _DummyMessage('/customization_request_reply cr_reply_denied', USER_ID)

    asyncio.run(cmd_customization_request_reply(message, config, state))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_denied')
    assert after is not None
    assert after.admin_response_text is None
    assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_unauthorized_user_is_blocked_by_middleware_for_customization_request_reply(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_request_reply cr_reply_hidden', UNKNOWN_ID)
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


def test_bootstrap_admin_reply_command_passes_middleware_without_user_access(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/customization_request_reply cr_reply', ADMIN_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    assert calls == ['handler-called']
    assert message.answers == []


def test_customization_request_reply_missing_ambiguous_and_short_prefix_are_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_ambiguous_one')
    _create_request(service, request_id='cr_reply_ambiguous_two')
    missing_arg = _DummyMessage('/customization_request_reply', ADMIN_ID)
    short_message = _DummyMessage('/customization_request_reply cr_x', ADMIN_ID)
    missing_message = _DummyMessage('/customization_request_reply cr_reply_missing_long', ADMIN_ID)
    ambiguous_message = _DummyMessage('/customization_request_reply cr_reply_ambiguous', ADMIN_ID)

    asyncio.run(cmd_customization_request_reply(missing_arg, config, _DummyState()))
    asyncio.run(cmd_customization_request_reply(short_message, config, _DummyState()))
    asyncio.run(cmd_customization_request_reply(missing_message, config, _DummyState()))
    asyncio.run(cmd_customization_request_reply(ambiguous_message, config, _DummyState()))

    assert missing_arg.answers == ['Použitie: /customization_request_reply <request_id>']
    assert short_message.answers == [
        'Požiadavku som nenašiel. Zadajte celý request_id alebo aspoň 8 znakov začiatku ID.'
    ]
    assert missing_message.answers == ['Požiadavku som nenašiel.']
    assert ambiguous_message.answers == [
        'Našiel som viac požiadaviek s týmto začiatkom ID. Použite dlhší request_id.'
    ]


def test_admin_reply_starts_text_prompt_and_preview_sends_nothing(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_start_abcdef', telegram_id=USER_ID)
    state = _DummyState()
    start_message = _DummyMessage('/customization_request_reply cr_reply_start', ADMIN_ID)

    asyncio.run(cmd_customization_request_reply(start_message, config, state))

    assert state.current_state == CustomizationRequestAdminResponseStates.waiting_response_text.state
    assert 'Napíšte odpoveď pre používateľa' in start_message.answers[-1]
    draft = state.data['customization_request_admin_response_draft']
    assert draft['request_id'] == 'cr_reply_start_abcdef'
    assert draft['target_telegram_id'] == USER_ID
    assert draft['response_kind'] == RESPONSE_KIND_ANSWER

    text_message = _DummyMessage('Toto je odpoveď správcu.', ADMIN_ID)
    asyncio.run(customization_request_response_text(text_message, state))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_start_abcdef')
    assert after is not None
    assert after.admin_response_text is None
    assert state.current_state == CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state
    assert 'Náhľad odpovede používateľovi' in text_message.answers[-1]
    assert 'Odoslať / Upraviť / Zrušiť' in text_message.answers[-1]


def test_admin_reply_cancel_sends_and_persists_nothing(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_cancel')
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_cancel', ADMIN_ID), config, state))
    asyncio.run(customization_request_response_text(_DummyMessage('Neodoslana odpoved.', ADMIN_ID), state))
    bot = _DummyBot()
    cancel_message = _DummyMessage('zrusit', ADMIN_ID)

    asyncio.run(
        customization_request_response_preview_decision(
            cancel_message,
            state,
            config,
            bot=bot,
            canonical_decision='cancel',
        )
    )

    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_cancel')
    assert after is not None
    assert after.admin_response_text is None
    assert after.response_delivery_status is None
    assert bot.sent == []
    assert state.cleared is True
    assert cancel_message.answers == ['Zrušené. Odpoveď nebola odoslaná.']


def test_admin_reply_edit_updates_draft_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_edit')
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_edit', ADMIN_ID), config, state))
    asyncio.run(customization_request_response_text(_DummyMessage('Povodna odpoved.', ADMIN_ID), state))

    asyncio.run(
        customization_request_response_preview_decision(
            _DummyMessage('upravit', ADMIN_ID),
            state,
            config,
            canonical_decision='edit',
        )
    )
    asyncio.run(customization_request_response_text(_DummyMessage('Upravena odpoved.', ADMIN_ID), state))

    draft = state.data['customization_request_admin_response_draft']
    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_edit')
    assert after is not None
    assert after.admin_response_text is None
    assert draft['response_text'] == 'Upravena odpoved.'
    assert state.current_state == CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state


def test_admin_reply_confirm_persists_before_send_and_marks_success(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_success', telegram_id=USER_ID)
    before_product_truth = [entry.to_payload() for entry in product_truth.list_capabilities()]
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_success', ADMIN_ID), config, state))
    asyncio.run(customization_request_response_text(_DummyMessage('Dobrý deň, tu je odpoveď.', ADMIN_ID), state))
    draft_before_confirm = dict(state.data['customization_request_admin_response_draft'])
    bot = _InspectingBot(service, 'cr_reply_success')

    asyncio.run(
        customization_request_response_preview_decision(
            _DummyMessage('odoslat', ADMIN_ID),
            state,
            config,
            bot=bot,
            canonical_decision='approve',
        )
    )

    assert bot.sent == [(USER_ID, 'Odpoveď správcu k vašej požiadavke:\n\nDobrý deň, tu je odpoveď.')]
    assert bot.record_before_send is not None
    assert bot.record_before_send.response_delivery_status == RESPONSE_DELIVERY_PENDING
    assert bot.record_before_send.admin_response_text == 'Dobrý deň, tu je odpoveď.'
    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_success')
    assert after is not None
    assert after.response_delivery_status == RESPONSE_DELIVERY_SUCCEEDED
    assert after.response_attempts == 1
    assert after.response_sent_at is not None
    assert after.response_sent_by == ADMIN_ID
    assert after.response_kind == RESPONSE_KIND_ANSWER
    assert after.responded_to_request_status == STATUS_CONFIRMED_PENDING_REVIEW
    assert after.status == STATUS_CONFIRMED_PENDING_REVIEW
    assert [entry.to_payload() for entry in product_truth.list_capabilities()] == before_product_truth
    assert state.cleared is True

    duplicate_state = _DummyState(
        {'customization_request_admin_response_draft': draft_before_confirm},
        CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state,
    )
    duplicate_bot = _DummyBot()
    duplicate_message = _DummyMessage('odoslat', ADMIN_ID)
    asyncio.run(
        customization_request_response_preview_decision(
            duplicate_message,
            duplicate_state,
            config,
            bot=duplicate_bot,
            canonical_decision='approve',
        )
    )
    duplicate_after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_success')
    assert duplicate_after is not None
    assert duplicate_after.response_attempts == 1
    assert duplicate_bot.sent == []
    assert duplicate_message.answers == ['Odpoveď už bola odoslaná používateľovi. Neodoslal som ju znova.']


def test_admin_reply_pending_duplicate_does_not_send_twice(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_pending_duplicate', telegram_id=USER_ID)
    state = _DummyState()
    asyncio.run(
        cmd_customization_request_reply(
            _DummyMessage('/customization_request_reply cr_reply_pending_duplicate', ADMIN_ID),
            config,
            state,
        )
    )
    asyncio.run(customization_request_response_text(_DummyMessage('Odpoveď.', ADMIN_ID), state))
    draft = dict(state.data['customization_request_admin_response_draft'])
    service.persist_customization_request_response_attempt(
        request_id=draft['request_id'],
        admin_telegram_id=ADMIN_ID,
        response_id=draft['response_id'],
        response_text=draft['response_text'],
        response_kind=draft['response_kind'],
    )
    bot = _DummyBot()
    duplicate_message = _DummyMessage('odoslat', ADMIN_ID)

    asyncio.run(
        customization_request_response_preview_decision(
            duplicate_message,
            state,
            config,
            bot=bot,
            canonical_decision='approve',
        )
    )

    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_pending_duplicate')
    assert after is not None
    assert after.response_delivery_status == RESPONSE_DELIVERY_PENDING
    assert after.response_attempts == 1
    assert bot.sent == []
    assert duplicate_message.answers == ['Odpoveď sa už odosiela. Neodoslal som ju znova.']


def test_admin_reply_failed_response_id_does_not_auto_retry(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_no_retry', telegram_id=USER_ID)
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_no_retry', ADMIN_ID), config, state))
    asyncio.run(customization_request_response_text(_DummyMessage('Odpoveď.', ADMIN_ID), state))
    draft = dict(state.data['customization_request_admin_response_draft'])
    service.persist_customization_request_response_attempt(
        request_id=draft['request_id'],
        admin_telegram_id=ADMIN_ID,
        response_id=draft['response_id'],
        response_text=draft['response_text'],
        response_kind=draft['response_kind'],
    )
    service.mark_response_delivery_failed(request_id=draft['request_id'], response_id=draft['response_id'])
    bot = _DummyBot()
    retry_message = _DummyMessage('odoslat', ADMIN_ID)

    asyncio.run(
        customization_request_response_preview_decision(
            retry_message,
            state,
            config,
            bot=bot,
            canonical_decision='approve',
        )
    )

    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_no_retry')
    assert after is not None
    assert after.response_delivery_status == RESPONSE_DELIVERY_FAILED
    assert after.response_attempts == 1
    assert bot.sent == []
    assert retry_message.answers == ['Odpoveď už je uložená ako nedoručená. Automaticky ju neposielam znova.']


def test_admin_reply_tampered_draft_target_cannot_redirect_delivery(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_tampered_target', telegram_id=USER_ID)
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_tampered_target', ADMIN_ID), config, state))
    asyncio.run(customization_request_response_text(_DummyMessage('Odpoveď ide pôvodnému používateľovi.', ADMIN_ID), state))
    draft = dict(state.data['customization_request_admin_response_draft'])
    draft['target_telegram_id'] = OTHER_USER_ID
    awaitable = state.update_data(customization_request_admin_response_draft=draft)
    asyncio.run(awaitable)
    bot = _DummyBot()

    asyncio.run(
        customization_request_response_preview_decision(
            _DummyMessage('odoslat', ADMIN_ID),
            state,
            config,
            bot=bot,
            canonical_decision='approve',
        )
    )

    assert bot.sent == [(USER_ID, 'Odpoveď správcu k vašej požiadavke:\n\nOdpoveď ide pôvodnému používateľovi.')]


def test_admin_reply_missing_bot_records_send_failed_missing_bot(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_missing_bot', telegram_id=USER_ID)
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_missing_bot', ADMIN_ID), config, state))
    asyncio.run(customization_request_response_text(_DummyMessage('Odpoveď bez bot objektu.', ADMIN_ID), state))

    asyncio.run(
        customization_request_response_preview_decision(
            _DummyMessage('odoslat', ADMIN_ID),
            state,
            config,
            bot=None,
            canonical_decision='approve',
        )
    )

    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_missing_bot')
    assert after is not None
    assert after.response_delivery_status == RESPONSE_DELIVERY_FAILED
    assert after.response_failed_reason == 'missing_bot'
    assert after.response_attempts == 1
    assert after.admin_response_text == 'Odpoveď bez bot objektu.'


def test_admin_reply_final_outbound_message_is_redacted(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_redacted', telegram_id=USER_ID)
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_redacted', ADMIN_ID), config, state))
    asyncio.run(
        customization_request_response_text(
            _DummyMessage(
                'password=supersecret token sk-secretTOKEN123 email person@example.com '
                'IBAN SK7700000000000000000000 phone +421 900 123 456',
                ADMIN_ID,
            ),
            state,
        )
    )
    bot = _DummyBot()

    asyncio.run(
        customization_request_response_preview_decision(
            _DummyMessage('odoslat', ADMIN_ID),
            state,
            config,
            bot=bot,
            canonical_decision='approve',
        )
    )

    assert len(bot.sent) == 1
    sent_text = bot.sent[0][1]
    assert '[REDACTED]' in sent_text
    assert 'supersecret' not in sent_text
    assert 'sk-secretTOKEN123' not in sent_text
    assert 'person@example.com' not in sent_text
    assert 'SK7700000000000000000000' not in sent_text
    assert '+421 900 123 456' not in sent_text


def test_admin_reply_failed_send_persists_safe_failure_without_retry(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_reply_failed', telegram_id=USER_ID)
    state = _DummyState()
    asyncio.run(cmd_customization_request_reply(_DummyMessage('/customization_request_reply cr_reply_failed', ADMIN_ID), config, state))
    asyncio.run(customization_request_response_text(_DummyMessage('Odpoveď na neskoršie doručenie.', ADMIN_ID), state))
    bot = _FailingBot()

    asyncio.run(
        customization_request_response_preview_decision(
            _DummyMessage('odoslat', ADMIN_ID),
            state,
            config,
            bot=bot,
            canonical_decision='approve',
        )
    )

    after = service.get_customization_request_by_id_for_admin(request_id='cr_reply_failed')
    assert after is not None
    assert after.admin_response_text == 'Odpoveď na neskoršie doručenie.'
    assert after.response_delivery_status == RESPONSE_DELIVERY_FAILED
    assert after.response_failed_reason == 'telegram_send_failed'
    assert after.response_attempts == 1
    assert after.response_sent_at is None
    assert bot.attempts == 1
    assert state.cleared is True


def test_admin_can_accept_pending_customization_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_accept', telegram_id=USER_ID)
    before = service.get_customization_request_by_id_for_admin(request_id='cr_review_accept')
    assert before is not None
    message = _DummyMessage('/customization_request_accept cr_review_accept', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(message, config))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_review_accept')
    assert after is not None
    assert after.status == STATUS_REVIEWED_ACCEPTED
    assert after.reviewed_by == ADMIN_ID
    assert after.reviewed_at is not None
    assert after.updated_at != before.updated_at
    assert after.admin_note is None
    assert message.answers == [
        'Po\u017eiadavka bola ozna\u010den\u00e1 ako prijat\u00e1 na neskor\u0161iu kontrolu. Neznamen\u00e1 to automatick\u00fa implement\u00e1ciu.'
    ]


def test_admin_can_reject_pending_customization_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_reject', telegram_id=USER_ID)
    before = service.get_customization_request_by_id_for_admin(request_id='cr_review_reject')
    assert before is not None
    message = _DummyMessage('/customization_request_reject cr_review_reject', ADMIN_ID)

    asyncio.run(cmd_customization_request_reject(message, config))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_review_reject')
    assert after is not None
    assert after.status == STATUS_REVIEWED_REJECTED
    assert after.reviewed_by == ADMIN_ID
    assert after.reviewed_at is not None
    assert after.updated_at != before.updated_at
    assert after.admin_note is None
    assert message.answers == ['Po\u017eiadavka bola ozna\u010den\u00e1 ako zamietnut\u00e1. Product Truth sa nezmenil.']


def test_non_admin_authorized_user_cannot_accept_or_reject_customization_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_denied')

    for handler, text in (
        (cmd_customization_request_accept, '/customization_request_accept cr_review_denied'),
        (cmd_customization_request_reject, '/customization_request_reject cr_review_denied'),
    ):
        message = _DummyMessage(text, USER_ID)
        asyncio.run(handler(message, config))
        after = service.get_customization_request_by_id_for_admin(request_id='cr_review_denied')
        assert after is not None
        assert after.status == STATUS_CONFIRMED_PENDING_REVIEW
        assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_unauthorized_user_is_blocked_by_middleware_for_customization_request_review(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    for text in (
        '/customization_request_accept cr_review_hidden',
        '/customization_request_reject cr_review_hidden',
    ):
        message = _DummyMessage(text, UNKNOWN_ID)
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


def test_bootstrap_admin_review_commands_pass_middleware_without_user_access(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    for text in (
        '/customization_request_accept cr_review',
        '/customization_request_reject cr_review',
    ):
        message = _DummyMessage(text, ADMIN_ID)
        calls: list[str] = []

        async def _handler(event, data):
            calls.append('handler-called')

        asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

        assert calls == ['handler-called']
        assert message.answers == []


def test_customization_request_review_missing_and_short_prefix_are_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    short_message = _DummyMessage('/customization_request_accept cr_x', ADMIN_ID)
    missing_message = _DummyMessage('/customization_request_reject cr_missing_long_prefix', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(short_message, config))
    asyncio.run(cmd_customization_request_reject(missing_message, config))

    assert short_message.answers == [
        'Po\u017eiadavku som nena\u0161iel. Zadajte cel\u00fd request_id alebo aspo\u0148 8 znakov za\u010diatku ID.'
    ]
    assert missing_message.answers == ['Po\u017eiadavku som nena\u0161iel.']


def test_customization_request_review_requires_request_id_argument(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    accept_message = _DummyMessage('/customization_request_accept', ADMIN_ID)
    reject_message = _DummyMessage('/customization_request_reject', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(accept_message, config))
    asyncio.run(cmd_customization_request_reject(reject_message, config))

    assert accept_message.answers == ['Pou\u017eitie: /customization_request_accept <request_id>']
    assert reject_message.answers == ['Pou\u017eitie: /customization_request_reject <request_id>']


def test_customization_request_review_already_processed_is_safe_and_idempotent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_once')
    accept_message = _DummyMessage('/customization_request_accept cr_review_once', ADMIN_ID)
    repeat_accept_message = _DummyMessage('/customization_request_accept cr_review_once', ADMIN_ID)
    reject_message = _DummyMessage('/customization_request_reject cr_review_once', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(accept_message, config))
    accepted = service.get_customization_request_by_id_for_admin(request_id='cr_review_once')
    assert accepted is not None
    asyncio.run(cmd_customization_request_accept(repeat_accept_message, config))
    asyncio.run(cmd_customization_request_reject(reject_message, config))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_review_once')
    assert after is not None
    assert after.status == STATUS_REVIEWED_ACCEPTED
    assert after.reviewed_by == ADMIN_ID
    assert after.reviewed_at == accepted.reviewed_at
    assert after.updated_at == accepted.updated_at
    assert repeat_accept_message.answers == ['Po\u017eiadavka u\u017e bola spracovan\u00e1.']
    assert reject_message.answers == ['Po\u017eiadavka u\u017e bola spracovan\u00e1.']


def test_customization_request_accept_already_rejected_is_safe_and_idempotent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_rejected_once')
    reject_message = _DummyMessage('/customization_request_reject cr_review_rejected_once', ADMIN_ID)
    repeat_reject_message = _DummyMessage('/customization_request_reject cr_review_rejected_once', ADMIN_ID)
    accept_message = _DummyMessage('/customization_request_accept cr_review_rejected_once', ADMIN_ID)

    asyncio.run(cmd_customization_request_reject(reject_message, config))
    rejected = service.get_customization_request_by_id_for_admin(request_id='cr_review_rejected_once')
    assert rejected is not None
    asyncio.run(cmd_customization_request_reject(repeat_reject_message, config))
    asyncio.run(cmd_customization_request_accept(accept_message, config))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_review_rejected_once')
    assert after is not None
    assert after.status == STATUS_REVIEWED_REJECTED
    assert after.reviewed_by == ADMIN_ID
    assert after.reviewed_at == rejected.reviewed_at
    assert after.updated_at == rejected.updated_at
    assert repeat_reject_message.answers == ['Po\u017eiadavka u\u017e bola spracovan\u00e1.']
    assert accept_message.answers == ['Po\u017eiadavka u\u017e bola spracovan\u00e1.']


def test_admin_can_review_cross_tenant_customization_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_other_user', telegram_id=OTHER_USER_ID)
    message = _DummyMessage('/customization_request_accept cr_review_other_user', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(message, config))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_review_other_user')
    assert after is not None
    assert after.telegram_id == OTHER_USER_ID
    assert after.status == STATUS_REVIEWED_ACCEPTED


def test_customization_request_review_has_no_downstream_side_effects(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_side_effects')
    before_product_truth = [entry.to_payload() for entry in product_truth.list_capabilities()]
    bot = _DummyBot()
    message = _DummyMessage('/customization_request_accept cr_review_side_effects', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(message, config))

    after = service.get_customization_request_by_id_for_admin(request_id='cr_review_side_effects')
    assert after is not None
    assert after.status == STATUS_REVIEWED_ACCEPTED
    assert [entry.to_payload() for entry in product_truth.list_capabilities()] == before_product_truth
    assert bot.sent == []
    assert not hasattr(service, 'convert_to_backlog')
    assert not hasattr(service, 'convert_to_product_truth_candidate')
    assert not hasattr(service, 'notify_admin')
    assert not hasattr(service, 'send_admin_notification')
    assert not hasattr(service, 'create_code_agent_handoff')


def test_reviewed_request_leaves_pending_list_but_remains_visible_in_detail(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_list_detail', title='Reviewed title')
    accept_message = _DummyMessage('/customization_request_accept cr_review_list_detail', ADMIN_ID)
    list_message = _DummyMessage('/customization_requests', ADMIN_ID)
    detail_message = _DummyMessage('/customization_request cr_review_list_detail', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(accept_message, config))
    asyncio.run(cmd_customization_requests(list_message, config))
    asyncio.run(cmd_customization_request_detail(detail_message, config))

    assert list_message.answers == ['Moment\u00e1lne nie s\u00fa \u017eiadne po\u017eiadavky \u010dakaj\u00face na kontrolu.']
    assert 'Reviewed title' in detail_message.answers[-1]
    assert 'status=reviewed_accepted' in detail_message.answers[-1]


def test_customization_request_review_prefix_lookup_is_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    _create_request(service, request_id='cr_review_unique_prefix_abcdef', title='Unique review')
    _create_request(service, request_id='cr_review_ambiguous_one', title='Ambiguous one')
    _create_request(service, request_id='cr_review_ambiguous_two', title='Ambiguous two')
    unique_message = _DummyMessage('/customization_request_accept cr_review_unique_prefix', ADMIN_ID)
    ambiguous_message = _DummyMessage('/customization_request_reject cr_review_ambiguous', ADMIN_ID)

    asyncio.run(cmd_customization_request_accept(unique_message, config))
    asyncio.run(cmd_customization_request_reject(ambiguous_message, config))

    unique = service.get_customization_request_by_id_for_admin(request_id='cr_review_unique_prefix_abcdef')
    ambiguous_one = service.get_customization_request_by_id_for_admin(request_id='cr_review_ambiguous_one')
    ambiguous_two = service.get_customization_request_by_id_for_admin(request_id='cr_review_ambiguous_two')
    assert unique is not None and unique.status == STATUS_REVIEWED_ACCEPTED
    assert ambiguous_one is not None and ambiguous_one.status == STATUS_CONFIRMED_PENDING_REVIEW
    assert ambiguous_two is not None and ambiguous_two.status == STATUS_CONFIRMED_PENDING_REVIEW
    assert ambiguous_message.answers == [
        'Na\u0161iel som viac po\u017eiadaviek s t\u00fdmto za\u010diatkom ID. Pou\u017eite dlh\u0161\u00ed request_id.'
    ]
