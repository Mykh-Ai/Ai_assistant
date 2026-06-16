from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice_followup import (
    INVOICE_FOLLOWUP_DECISION_MARK_PAID,
    INVOICE_FOLLOWUP_DECISION_MUTE,
    INVOICE_FOLLOWUP_DECISION_REMIND_LATER,
    _callback_data,
    invoice_followup_callback,
)
from bot.services.access_control import AccessControlService
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db
from bot.services.invoice_followup_service import (
    DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID,
    PAYMENT_STATUS_PAID,
    REMINDER_STATUS_MUTED,
    REMINDER_STATUS_SNOOZED,
    InvoiceFollowupService,
)
from bot.services.invoice_followup_scheduler import send_due_invoice_followups_once
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService


USER_A = 501001
USER_B = 501002


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str = '', user_id: int = USER_A) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []
        self.reply_markups: list[object] = []
        self.cleared_reply_markups: list[object | None] = []
        self.fail_edit_reply_markup = False

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)
        self.reply_markups.append(kwargs.get('reply_markup'))

    async def edit_reply_markup(self, **kwargs) -> None:
        if self.fail_edit_reply_markup:
            raise RuntimeError('edit_reply_markup_failed')
        self.cleared_reply_markups.append(kwargs.get('reply_markup'))


class _DummyCallback:
    def __init__(self, *, data: str, user_id: int, message: _DummyMessage | None = None) -> None:
        self.data = data
        self.from_user = _DummyUser(user_id)
        self.message = message
        self.answers: list[tuple[str | None, bool | None]] = []

    async def answer(self, text: str | None = None, show_alert: bool | None = None, **kwargs) -> None:
        self.answers.append((text, show_alert))


class _DummyBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str, object | None]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.sent_messages.append((chat_id, text, kwargs.get('reply_markup')))


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'invoice-followup-handler.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset({USER_A, USER_B}),
        admin_telegram_user_ids=frozenset(),
        invoice_followup_check_interval_seconds=60,
        invoice_followup_notification_cooldown_hours=24,
    )


def _setup_account(db_path: Path, telegram_id: int) -> int:
    SupplierService(db_path).create_or_replace(
        SupplierProfile(
            telegram_id=telegram_id,
            name=f'Dodavatel {telegram_id}',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Hlavna 1, Bratislava',
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
            name=f'Odberatel {telegram_id}',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='Dlha 2, Kosice',
            email='customer@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    contact = ContactService(db_path).get_by_name(telegram_id, f'Odberatel {telegram_id}')
    assert contact is not None and contact.id is not None
    return contact.id


def _create_invoice(db_path: Path, *, supplier_telegram_id: int, contact_id: int, due_date: str = '2026-06-10') -> int:
    return InvoiceService(db_path).create_invoice_with_items(
        supplier_telegram_id=supplier_telegram_id,
        contact_id=contact_id,
        issue_date='2026-06-01',
        delivery_date='2026-06-01',
        due_date=due_date,
        due_days=14,
        total_amount=120.0,
        currency='EUR',
        status='pripravena',
        invoice_number='20260001',
        items=[
            CreateInvoiceItemPayload(
                description_raw='servis',
                description_normalized='Servis',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=120.0,
                total_price=120.0,
            )
        ],
    )


def _setup_invoice(config: Config, *, telegram_id: int = USER_A) -> int:
    init_db(config.db_path)
    contact_id = _setup_account(config.db_path, telegram_id)
    return _create_invoice(config.db_path, supplier_telegram_id=telegram_id, contact_id=contact_id)


def test_automatic_due_date_check_sends_overdue_invoice_card_with_three_decisions(tmp_path: Path) -> None:
    config = _config(tmp_path)
    invoice_id = _setup_invoice(config)
    bot = _DummyBot()

    result = asyncio.run(send_due_invoice_followups_once(bot=bot, config=config))

    assert result.reminders_sent == 1
    assert bot.sent_messages[0][0] == USER_A
    assert 'Fakture 20260001 uplynula splatnost' in bot.sent_messages[0][1]
    keyboard = bot.sent_messages[0][2]
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert [button.text for button in buttons] == [
        'Oznacit ako zaplatenu',
        'Pripomenut neskor',
        'Viac nepripominat',
    ]
    assert buttons[0].callback_data == _callback_data(INVOICE_FOLLOWUP_DECISION_MARK_PAID, invoice_id)
    state = InvoiceFollowupService(config.db_path).get_state(invoice_id=invoice_id)
    assert state is not None
    assert state.remind_after is not None
    assert state.reminder_status == 'active'


def test_automatic_due_date_check_sends_nothing_when_no_due_invoices(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    contact_id = _setup_account(config.db_path, USER_A)
    _create_invoice(config.db_path, supplier_telegram_id=USER_A, contact_id=contact_id, due_date='2999-01-01')
    bot = _DummyBot()

    result = asyncio.run(send_due_invoice_followups_once(bot=bot, config=config))

    assert result.reminders_sent == 0
    assert bot.sent_messages == []


def test_automatic_due_date_check_skips_blocked_user_even_if_invoice_is_due(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_invoice(config, telegram_id=USER_A)
    AccessControlService(config.db_path).block_user(telegram_id=USER_A, decided_by=USER_B)
    bot = _DummyBot()

    result = asyncio.run(send_due_invoice_followups_once(bot=bot, config=config))

    assert result.skipped_unauthorized_suppliers == 1
    assert result.reminders_sent == 0
    assert bot.sent_messages == []


def test_mark_paid_callback_persists_state_and_shows_drive_stub(tmp_path: Path) -> None:
    config = _config(tmp_path)
    invoice_id = _setup_invoice(config)
    source_message = _DummyMessage(user_id=USER_A)
    callback = _DummyCallback(
        data=_callback_data(INVOICE_FOLLOWUP_DECISION_MARK_PAID, invoice_id),
        user_id=USER_A,
        message=source_message,
    )

    asyncio.run(invoice_followup_callback(callback, config))

    state = InvoiceFollowupService(config.db_path).get_state(invoice_id=invoice_id)
    assert state is not None
    assert state.payment_status == PAYMENT_STATUS_PAID
    assert state.reminder_status == REMINDER_STATUS_MUTED
    assert state.drive_archive_status == DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID
    assert source_message.cleared_reply_markups == [None]
    assert 'Fakturu som oznacil ako zaplatenu.' in source_message.answers[-1]
    assert 'Google Drive este nie je aktivna' in source_message.answers[-1]
    assert 'ostava ulozena lokalne' in source_message.answers[-1]


def test_remind_later_callback_persists_snoozed_state_without_drive_stub(tmp_path: Path) -> None:
    config = _config(tmp_path)
    invoice_id = _setup_invoice(config)
    source_message = _DummyMessage(user_id=USER_A)
    callback = _DummyCallback(
        data=_callback_data(INVOICE_FOLLOWUP_DECISION_REMIND_LATER, invoice_id),
        user_id=USER_A,
        message=source_message,
    )

    asyncio.run(invoice_followup_callback(callback, config))

    state = InvoiceFollowupService(config.db_path).get_state(invoice_id=invoice_id)
    assert state is not None
    assert state.reminder_status == REMINDER_STATUS_SNOOZED
    assert state.remind_after is not None
    assert source_message.cleared_reply_markups == [None]
    assert 'Dobre, pripomeniem neskor.' in source_message.answers[-1]
    assert 'Google Drive' not in source_message.answers[-1]


def test_mute_callback_persists_muted_state_without_drive_upload_claim(tmp_path: Path) -> None:
    config = _config(tmp_path)
    invoice_id = _setup_invoice(config)
    source_message = _DummyMessage(user_id=USER_A)
    callback = _DummyCallback(
        data=_callback_data(INVOICE_FOLLOWUP_DECISION_MUTE, invoice_id),
        user_id=USER_A,
        message=source_message,
    )

    asyncio.run(invoice_followup_callback(callback, config))

    state = InvoiceFollowupService(config.db_path).get_state(invoice_id=invoice_id)
    assert state is not None
    assert state.reminder_status == REMINDER_STATUS_MUTED
    assert source_message.cleared_reply_markups == [None]
    assert 'uz nebudem pripominat' in source_message.answers[-1]
    assert 'Google Drive' not in source_message.answers[-1]


def test_callback_rejects_invoice_from_another_supplier(tmp_path: Path) -> None:
    config = _config(tmp_path)
    invoice_id = _setup_invoice(config, telegram_id=USER_B)
    callback = _DummyCallback(
        data=_callback_data(INVOICE_FOLLOWUP_DECISION_MARK_PAID, invoice_id),
        user_id=USER_A,
        message=_DummyMessage(user_id=USER_A),
    )

    asyncio.run(invoice_followup_callback(callback, config))

    assert callback.answers == [('Tato pripomienka uz nie je dostupna pre vas ucet.', True)]
    assert callback.message is not None
    assert callback.message.cleared_reply_markups == []
    assert InvoiceFollowupService(config.db_path).get_state(invoice_id=invoice_id) is None


def test_keyboard_cleanup_failure_does_not_roll_back_successful_decision(tmp_path: Path) -> None:
    config = _config(tmp_path)
    invoice_id = _setup_invoice(config)
    source_message = _DummyMessage(user_id=USER_A)
    source_message.fail_edit_reply_markup = True
    callback = _DummyCallback(
        data=_callback_data(INVOICE_FOLLOWUP_DECISION_MUTE, invoice_id),
        user_id=USER_A,
        message=source_message,
    )

    asyncio.run(invoice_followup_callback(callback, config))

    state = InvoiceFollowupService(config.db_path).get_state(invoice_id=invoice_id)
    assert state is not None
    assert state.reminder_status == REMINDER_STATUS_MUTED
    assert source_message.cleared_reply_markups == []
    assert 'uz nebudem pripominat' in source_message.answers[-1]
    assert callback.answers == [(None, None)]
