from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from aiogram.types import CallbackQuery, User

from bot.config import Config
from bot.services.active_fsm_guard import ACTIVE_FSM_EXPIRED_MESSAGE, ACTIVE_FSM_LAST_ACTIVITY_AT_KEY
from bot.handlers.access_admin import CustomizationRequestAdminResponseStates
from bot.handlers.contacts import ContactStates
from bot.handlers.decision_callbacks import _dispatch_decision_token, decision_callback
from bot.handlers.invoice import CustomizationRequestStates, InvoiceStates
from bot.keyboards.decision import DECISION_APPROVE, DECISION_CANCEL, DECISION_EDIT, DECISION_NO, DECISION_YES
from bot.services.authorization import TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.customization_requests import CustomizationRequestService
from bot.services.db import init_db, managed_connection
from bot.services.invoice_service import InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService


ADMIN_ID = 950000
AUTHORIZED_ID = 950001
UNKNOWN_ID = 950002


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, user_id: int = AUTHORIZED_ID) -> None:
        self.from_user = _DummyUser(user_id)
        self.text = ''
        self.answers: list[str] = []
        self.documents: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)

    async def answer_document(self, document, caption: str | None = None, **kwargs) -> None:
        self.documents.append(caption or '')


class _CallbackSourceMessage(_DummyMessage):
    def __init__(self, user_id: int = AUTHORIZED_ID) -> None:
        super().__init__(user_id)
        self.reply_markup_edits: list[object | None] = []
        self.fail_edit_reply_markup = False

    async def edit_reply_markup(self, *, reply_markup=None) -> None:
        if self.fail_edit_reply_markup:
            raise RuntimeError('edit_reply_markup_failed')
        self.reply_markup_edits.append(reply_markup)


class _DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.sent.append((telegram_id, text))


class _DummyState:
    def __init__(self, data: dict | None = None, current_state=None) -> None:
        self.data = data or {}
        self.current_state = current_state
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state

    async def clear(self) -> None:
        self.cleared = True
        self.current_state = None
        self.data.clear()

    async def get_state(self):
        return self.current_state


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'decision-callbacks.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset(),
        admin_telegram_user_ids=frozenset({ADMIN_ID}),
    )


def _setup_supplier_and_contact(db_path: Path, telegram_id: int = AUTHORIZED_ID) -> int:
    init_db(db_path)
    SupplierService(db_path).create_or_replace(
        SupplierProfile(
            telegram_id=telegram_id,
            name='Dodavatel',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Bratislava',
            iban='SK3112000000198742637541',
            swift='TATRSKBX',
            email='supplier@example.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    ContactService(db_path).create_or_replace(
        ContactProfile(
            supplier_telegram_id=telegram_id,
            name='Tech Company s.r.o.',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='Kosice 1',
            email='contact@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    contact = ContactService(db_path).get_by_name(telegram_id, 'Tech Company s.r.o.')
    assert contact is not None and contact.id is not None
    return contact.id


def _draft(contact_id: int) -> dict:
    return {
        'customer_name': 'Tech Company s.r.o.',
        'contact_id': contact_id,
        'service_short_name': 'servis',
        'service_display_name': 'Servis zariadenia',
        'quantity': 1,
        'unit_price': 100,
        'unit': 'ks',
        'amount': 100,
        'currency': 'EUR',
        'issue_date': '2026-04-12',
        'delivery_date': '2026-04-12',
        'due_days': 14,
        'due_date': '2026-04-26',
    }


def _customization_request_draft(request_id: str = 'cr_callback') -> dict:
    return {
        'request_id': request_id,
        'requester_telegram_id': AUTHORIZED_ID,
        'supplier_telegram_id': AUTHORIZED_ID,
        'workspace_id': f'telegram:{AUTHORIZED_ID}',
        'source_channel': 'text',
        'source_triage_class': 'customization_request_candidate',
        'source_capability_id': None,
        'source_topic_id': None,
        'normalized_title': 'Po\u017eiadavka: Mesa\u010dn\u00fd report',
        'normalized_summary': 'Chcem mesa\u010dn\u00fd report tr\u017eieb.',
        'redacted_original_text': 'Chcem mesa\u010dn\u00fd report tr\u017eieb.',
        'raw_text_hash': '0' * 64,
        'confidence': 0.8,
    }


def _active_fsm_metadata(*, minutes_ago: int = 0) -> dict:
    return {
        ACTIVE_FSM_LAST_ACTIVITY_AT_KEY: (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat(),
    }

def _callback(user_id: int, data: str, source_message: object | None = None) -> CallbackQuery:
    callback = CallbackQuery(
        id='callback-id',
        from_user=User(id=user_id, is_bot=False, first_name='Test'),
        chat_instance='chat-instance',
        data=data,
    )
    answers: list[tuple[str | None, bool | None]] = []

    async def _answer(text: str | None = None, show_alert: bool | None = None, **kwargs) -> None:
        answers.append((text, show_alert))

    object.__setattr__(callback, 'answer', _answer)
    object.__setattr__(callback, 'answers', answers)
    if source_message is not None:
        object.__setattr__(callback, 'message', source_message)
    return callback


def test_unauthorized_callback_cannot_trigger_side_effects(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    callback = _callback(UNKNOWN_ID, 'decision:approve')
    state = _DummyState(current_state=InvoiceStates.waiting_confirm.state)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')

    asyncio.run(
        TelegramUserAuthorizationMiddleware()(
            _handler,
            callback,
            {'config': config, 'state': state},
        )
    )

    assert calls == []
    assert state.cleared is True
    assert callback.answers == [(UNAUTHORIZED_MESSAGE, True)]


def test_stale_callback_is_rejected_without_dispatch(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    callback = _callback(AUTHORIZED_ID, 'decision:approve')
    state = _DummyState(current_state=None)

    asyncio.run(decision_callback(callback, state, config))

    assert callback.answers == [('Toto rozhodnutie už nie je dostupné. Pokračujte aktuálnym krokom v chate.', True)]
    assert state.cleared is False


def test_legacy_decision_callback_with_missing_timestamp_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_legacy'),
            'customization_request_saved_id': None,
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )
    callback = _callback(AUTHORIZED_ID, 'decision:approve')

    asyncio.run(decision_callback(callback, state, config))

    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    ) == []
    assert state.cleared is True
    assert callback.answers == [(ACTIVE_FSM_EXPIRED_MESSAGE, True)]


def test_stale_decision_callback_with_old_timestamp_fails_closed(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_stale'),
            'customization_request_saved_id': None,
            **_active_fsm_metadata(minutes_ago=60),
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )
    callback = _callback(AUTHORIZED_ID, 'decision:approve')

    asyncio.run(decision_callback(callback, state, config))

    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    ) == []
    assert state.cleared is True
    assert callback.answers == [(ACTIVE_FSM_EXPIRED_MESSAGE, True)]

def test_button_approve_on_invoice_preview_uses_same_finalization_path(tmp_path: Path, monkeypatch) -> None:
    contact_id = _setup_supplier_and_contact(tmp_path / 'invoice-approve.db')
    config = _config(tmp_path)
    config = Config(**{**config.__dict__, 'db_path': tmp_path / 'invoice-approve.db'})

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)
    message = _DummyMessage()
    state = _DummyState({'invoice_draft': _draft(contact_id)}, InvoiceStates.waiting_confirm.state)

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_APPROVE,
            current_state=InvoiceStates.waiting_confirm.state,
            message=message,
            state=state,
            config=config,
        )
    )

    assert handled is True
    assert state.cleared is True
    invoice = InvoiceService(config.db_path).get_invoice_by_number('20260001')
    assert invoice is not None
    assert invoice.status == 'pripravena'
    assert message.documents
    assert message.answers[-1] == 'Faktúra 20260001 bola vytvorená.'


def test_button_cancel_on_invoice_preview_uses_same_cancel_path(tmp_path: Path) -> None:
    contact_id = _setup_supplier_and_contact(tmp_path / 'invoice-cancel.db')
    config = _config(tmp_path)
    config = Config(**{**config.__dict__, 'db_path': tmp_path / 'invoice-cancel.db'})
    message = _DummyMessage()
    state = _DummyState({'invoice_draft': _draft(contact_id)}, InvoiceStates.waiting_confirm.state)

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_CANCEL,
            current_state=InvoiceStates.waiting_confirm.state,
            message=message,
            state=state,
            config=config,
        )
    )

    assert handled is True
    assert state.cleared is True
    assert message.answers[-1] == 'Návrh faktúry bol zrušený.'
    assert InvoiceService(config.db_path).get_invoice_by_number('20260001') is None


def test_decision_callback_customization_approve_routes_and_saves(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_wrapper_approve'),
            'customization_request_saved_id': None,
            **_active_fsm_metadata(),
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )
    callback = _callback(AUTHORIZED_ID, 'decision:approve')

    asyncio.run(decision_callback(callback, state, config))

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    )
    assert len(records) == 1
    assert records[0].request_id == 'cr_callback_wrapper_approve'
    assert state.cleared is True
    assert callback.answers[-1] == (None, None)


def test_decision_callback_customization_cancel_routes_and_saves_nothing(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_wrapper_cancel'),
            'customization_request_saved_id': None,
            **_active_fsm_metadata(),
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )
    callback = _callback(AUTHORIZED_ID, 'decision:cancel')

    asyncio.run(decision_callback(callback, state, config))

    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    ) == []
    assert state.cleared is True
    assert any(answer[0] == 'Zru\u0161en\u00e9. Po\u017eiadavku som neulo\u017eil.' for answer in callback.answers)
    assert callback.answers[-1] == (None, None)


def test_decision_callback_customization_edit_routes_to_text_edit(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_wrapper_edit'),
            'customization_request_saved_id': None,
            **_active_fsm_metadata(),
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )
    callback = _callback(AUTHORIZED_ID, 'decision:edit')

    asyncio.run(decision_callback(callback, state, config))

    assert state.current_state == CustomizationRequestStates.waiting_edit_text
    assert state.cleared is False
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    ) == []
    assert any('n\u00e1zov a zhrnutie' in str(answer[0]) for answer in callback.answers)
    assert callback.answers[-1] == (None, None)


def test_button_approve_on_customization_preview_saves_one_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage()
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_approve'),
            'customization_request_saved_id': None,
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_APPROVE,
            current_state=CustomizationRequestStates.waiting_preview_decision.state,
            message=message,
            state=state,
            config=config,
        )
    )

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    )
    assert handled is True
    assert len(records) == 1
    assert records[0].request_id == 'cr_callback_approve'
    assert state.cleared is True


def test_button_cancel_on_customization_preview_saves_nothing_and_clears(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage()
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_cancel'),
            'customization_request_saved_id': None,
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_CANCEL,
            current_state=CustomizationRequestStates.waiting_preview_decision.state,
            message=message,
            state=state,
            config=config,
        )
    )

    assert handled is True
    assert state.cleared is True
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    ) == []


def test_button_edit_on_customization_preview_transitions_to_text_edit(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage()
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_edit'),
            'customization_request_saved_id': None,
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_EDIT,
            current_state=CustomizationRequestStates.waiting_preview_decision.state,
            message=message,
            state=state,
            config=config,
        )
    )

    assert handled is True
    assert state.current_state == CustomizationRequestStates.waiting_edit_text
    assert 'n\u00e1zov a zhrnutie' in message.answers[-1]


def test_stale_duplicate_customization_button_approve_does_not_save_twice(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage()
    state = _DummyState(
        {
            'customization_request_draft': _customization_request_draft('cr_callback_duplicate'),
            'customization_request_saved_id': None,
        },
        CustomizationRequestStates.waiting_preview_decision.state,
    )

    first = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_APPROVE,
            current_state=CustomizationRequestStates.waiting_preview_decision.state,
            message=message,
            state=state,
            config=config,
        )
    )
    duplicate = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_APPROVE,
            current_state=CustomizationRequestStates.waiting_preview_decision.state,
            message=message,
            state=state,
            config=config,
        )
    )

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=AUTHORIZED_ID,
    )
    assert first is True
    assert duplicate is True
    assert len(records) == 1


def test_button_approve_on_admin_response_preview_sends_one_response(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    service.create_confirmed_customization_request(
        request_id='cr_callback_admin_response',
        telegram_id=AUTHORIZED_ID,
        supplier_telegram_id=AUTHORIZED_ID,
        workspace_id=f'telegram:{AUTHORIZED_ID}',
        source_channel='text',
        source_triage_class='customization_request_candidate',
        normalized_title='Mesačný report',
        normalized_summary='Používateľ chce report.',
    )
    draft = {
        'response_id': 'crr_callback_admin_response',
        'request_id': 'cr_callback_admin_response',
        'target_telegram_id': AUTHORIZED_ID,
        'target_workspace_id': f'telegram:{AUTHORIZED_ID}',
        'admin_telegram_id': ADMIN_ID,
        'response_kind': 'answer',
        'response_text': 'Tu je odpoveď správcu.',
        'request_status_at_draft': 'confirmed_pending_review',
        'request_title_preview': 'Mesačný report',
        'created_at': '2026-05-23T00:00:00Z',
    }
    message = _DummyMessage(user_id=ADMIN_ID)
    state = _DummyState(
        {'customization_request_admin_response_draft': draft},
        CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state,
    )
    bot = _DummyBot()

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_APPROVE,
            current_state=CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state,
            message=message,
            state=state,
            config=config,
            bot=bot,
        )
    )

    after = service.get_customization_request_by_id_for_admin(request_id='cr_callback_admin_response')
    assert handled is True
    assert bot.sent == [(AUTHORIZED_ID, 'Odpoveď správcu k vašej požiadavke:\n\nTu je odpoveď správcu.')]
    assert after is not None
    assert after.response_delivery_status == 'send_succeeded'
    assert after.response_attempts == 1
    assert state.cleared is True


def test_stale_duplicate_admin_response_button_does_not_send_twice(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = CustomizationRequestService(config.db_path)
    service.create_confirmed_customization_request(
        request_id='cr_callback_admin_response_duplicate',
        telegram_id=AUTHORIZED_ID,
        supplier_telegram_id=AUTHORIZED_ID,
        workspace_id=f'telegram:{AUTHORIZED_ID}',
        source_channel='text',
        source_triage_class='customization_request_candidate',
        normalized_title='Mesačný report',
        normalized_summary='Používateľ chce report.',
    )
    draft = {
        'response_id': 'crr_callback_admin_response_duplicate',
        'request_id': 'cr_callback_admin_response_duplicate',
        'target_telegram_id': AUTHORIZED_ID,
        'target_workspace_id': f'telegram:{AUTHORIZED_ID}',
        'admin_telegram_id': ADMIN_ID,
        'response_kind': 'answer',
        'response_text': 'Jedna odpoveď.',
        'request_status_at_draft': 'confirmed_pending_review',
        'request_title_preview': 'Mesačný report',
        'created_at': '2026-05-23T00:00:00Z',
    }
    first_state = _DummyState(
        {'customization_request_admin_response_draft': dict(draft)},
        CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state,
    )
    duplicate_state = _DummyState(
        {'customization_request_admin_response_draft': dict(draft)},
        CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state,
    )
    first_bot = _DummyBot()
    duplicate_bot = _DummyBot()

    first = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_APPROVE,
            current_state=CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state,
            message=_DummyMessage(user_id=ADMIN_ID),
            state=first_state,
            config=config,
            bot=first_bot,
        )
    )
    duplicate_message = _DummyMessage(user_id=ADMIN_ID)
    duplicate = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_APPROVE,
            current_state=CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state,
            message=duplicate_message,
            state=duplicate_state,
            config=config,
            bot=duplicate_bot,
        )
    )

    after = service.get_customization_request_by_id_for_admin(
        request_id='cr_callback_admin_response_duplicate'
    )
    assert first is True
    assert duplicate is True
    assert first_bot.sent == [(AUTHORIZED_ID, 'Odpoveď správcu k vašej požiadavke:\n\nJedna odpoveď.')]
    assert duplicate_bot.sent == []
    assert duplicate_message.answers == ['Odpoveď už bola odoslaná používateľovi. Neodoslal som ju znova.']
    assert after is not None
    assert after.response_attempts == 1


def test_alias_confirmation_buttons_yes_and_no(tmp_path: Path, monkeypatch) -> None:
    contact_id = _setup_supplier_and_contact(tmp_path / 'alias.db')
    config = _config(tmp_path)
    config = Config(**{**config.__dict__, 'db_path': tmp_path / 'alias.db'})
    built_preview: list[str] = []

    async def _fake_build_preview(**kwargs) -> None:
        built_preview.append(kwargs['parsed_draft']['customer_name'])

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_preview)
    state = _DummyState(
        {
            'invoice_partial_draft': {
                'request_id': 'r1',
                'raw_text': 'raw',
                'parsed_draft': {},
                'candidate_text': 'Tech Co',
                'candidate_contact_id': contact_id,
            }
        },
        InvoiceStates.waiting_customer_alias_confirm.state,
    )

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_YES,
            current_state=InvoiceStates.waiting_customer_alias_confirm.state,
            message=_DummyMessage(),
            state=state,
            config=config,
        )
    )

    assert handled is True
    assert built_preview == ['Tech Company s.r.o.']
    with managed_connection(config.db_path) as connection:
        row = connection.execute(
            'SELECT target_id FROM confirmed_semantic_alias WHERE alias_text = ?',
            ('Tech Co',),
        ).fetchone()
    assert row is not None and row[0] == contact_id

    no_state = _DummyState(
        {'invoice_partial_draft': {'parsed_draft': {}, 'candidate_text': 'Tech Co', 'candidate_contact_id': contact_id}},
        InvoiceStates.waiting_customer_alias_confirm.state,
    )
    no_message = _DummyMessage()
    handled_no = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_NO,
            current_state=InvoiceStates.waiting_customer_alias_confirm.state,
            message=no_message,
            state=no_state,
            config=config,
        )
    )

    assert handled_no is True
    assert no_state.current_state == InvoiceStates.waiting_slot_clarification
    assert 'spresnite názov odberateľa' in no_message.answers[-1]


def test_contact_save_and_cancel_buttons(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier_and_contact(config.db_path)
    intake_state = _DummyState(
        {
            'contact_intake_draft': {
                'name': 'ZS s.r.o.',
                'ico': '12345678',
                'dic': '1234567890',
                'ic_dph': '',
                'address': 'Hlavná 1, Košice',
                'email': 'kontakt@zs.sk',
                'contact_person': '',
                'contract_path': 'storage/contracts/test.pdf',
            }
        },
        ContactStates.intake_confirm.state,
    )

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_YES,
            current_state=ContactStates.intake_confirm.state,
            message=_DummyMessage(),
            state=intake_state,
            config=config,
        )
    )

    assert handled is True
    assert ContactService(config.db_path).get_by_name(AUTHORIZED_ID, 'ZS s.r.o.') is not None

    manual_state = _DummyState(
        {
            'name': 'Manual ZS s.r.o.',
            'ico': '12345678',
            'dic': '1234567890',
            'ic_dph': '',
            'address': 'Hlavná 1, Košice',
            'email': 'manual@zs.sk',
            'contact_person': '',
        },
        ContactStates.confirm.state,
    )
    cancel_message = _DummyMessage()
    handled_cancel = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_NO,
            current_state=ContactStates.confirm.state,
            message=cancel_message,
            state=manual_state,
            config=config,
        )
    )

    assert handled_cancel is True
    assert manual_state.cleared is True
    assert ContactService(config.db_path).get_by_name(AUTHORIZED_ID, 'Manual ZS s.r.o.') is None
    assert '/contact' in cancel_message.answers[-1]


def test_button_yes_on_mark_existing_invoice_paid_routes_to_same_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _mark_paid(**kwargs) -> None:
        calls.append(kwargs['canonical_decision'])

    monkeypatch.setattr('bot.handlers.decision_callbacks.invoice_mark_existing_invoice_paid_confirm', _mark_paid)
    state = _DummyState(current_state=InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state)

    handled = asyncio.run(
        _dispatch_decision_token(
            token=DECISION_YES,
            current_state=InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state,
            message=_DummyMessage(),
            state=state,
            config=_config(tmp_path),
        )
    )

    assert handled is True
    assert calls == [DECISION_YES]


def test_mark_existing_invoice_paid_yes_and_no_buttons_clear_inline_keyboard(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _mark_paid(**kwargs) -> None:
        calls.append(kwargs['canonical_decision'])

    monkeypatch.setattr('bot.handlers.decision_callbacks.invoice_mark_existing_invoice_paid_confirm', _mark_paid)

    for token in (DECISION_YES, DECISION_NO):
        source_message = _CallbackSourceMessage()
        callback = _callback(AUTHORIZED_ID, f'decision:{token}', source_message=source_message)
        state = _DummyState(
            data=_active_fsm_metadata(),
            current_state=InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state,
        )

        asyncio.run(decision_callback(callback, state, _config(tmp_path)))

        assert source_message.reply_markup_edits == [None]
        assert callback.answers[-1] == (None, None)

    assert calls == [DECISION_YES, DECISION_NO]


def test_stale_mark_existing_invoice_paid_button_is_removed_without_dispatch(tmp_path: Path) -> None:
    source_message = _CallbackSourceMessage()
    callback = _callback(AUTHORIZED_ID, 'decision:yes', source_message=source_message)
    state = _DummyState(
        data=_active_fsm_metadata(minutes_ago=60),
        current_state=InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state,
    )

    asyncio.run(decision_callback(callback, state, _config(tmp_path)))

    assert source_message.reply_markup_edits == [None]
    assert state.cleared is True
    assert callback.answers == [(ACTIVE_FSM_EXPIRED_MESSAGE, True)]


def test_shared_decision_keyboard_cleanup_failure_is_logged_without_reversing_dispatch(monkeypatch, tmp_path: Path, caplog) -> None:
    calls: list[str] = []

    async def _mark_paid(**kwargs) -> None:
        calls.append(kwargs['canonical_decision'])

    monkeypatch.setattr('bot.handlers.decision_callbacks.invoice_mark_existing_invoice_paid_confirm', _mark_paid)
    source_message = _CallbackSourceMessage()
    source_message.fail_edit_reply_markup = True
    callback = _callback(AUTHORIZED_ID, 'decision:yes', source_message=source_message)
    state = _DummyState(
        data=_active_fsm_metadata(),
        current_state=InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state,
    )

    with caplog.at_level('ERROR'):
        asyncio.run(decision_callback(callback, state, _config(tmp_path)))

    assert calls == [DECISION_YES]
    assert callback.answers[-1] == (None, None)
    assert 'Failed to clear shared decision inline keyboard' in caplog.text
