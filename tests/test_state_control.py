from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import InvoiceStates
from bot.handlers.state_control import (
    IDLE_CANCEL_MESSAGE,
    PERSISTED_EDIT_CANCELLED_MESSAGE,
    STATE_CANCELLED_MESSAGE,
    cancel_alias,
    cancel_current_state,
)
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService


class _DummyMessage:
    def __init__(self, text: str = '/cancel') -> None:
        self.text = text
        self.from_user = type('U', (), {'id': 111})()
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self, current_state: str | None, data: dict | None = None) -> None:
        self.current_state = current_state
        self.data = dict(data or {})
        self.cleared = False

    async def get_state(self) -> str | None:
        return self.current_state

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.cleared = True
        self.current_state = None
        self.data.clear()


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'state-control.db',
        storage_dir=tmp_path,
    )


def test_cancel_idle_state_reports_idle(tmp_path: Path) -> None:
    message = _DummyMessage('/cancel')
    state = _DummyState(None)

    asyncio.run(cancel_current_state(message=message, state=state, config=_config(tmp_path)))

    assert state.cleared is True
    assert message.answers == [IDLE_CANCEL_MESSAGE]


def test_cancel_alias_clears_edit_scope_without_touching_data(tmp_path: Path) -> None:
    message = _DummyMessage('відмінити')
    state = _DummyState(InvoiceStates.waiting_edit_scope.state, {'edit_invoice_id': 10})

    asyncio.run(cancel_alias(message, state, _config(tmp_path)))

    assert state.cleared is True
    assert message.answers == [STATE_CANCELLED_MESSAGE]


def test_cancel_persisted_post_edit_keeps_invoice(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    SupplierService(config.db_path).create_or_replace(
        SupplierProfile(
            telegram_id=111,
            name='S',
            ico='1',
            dic='1',
            ic_dph='',
            address='A',
            iban='SK1',
            swift='ABCD',
            email='a@a.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    invoice_id = InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        issue_date='2026-04-30',
        delivery_date='2026-04-30',
        due_date='2026-05-14',
        due_days=14,
        total_amount=10,
        currency='EUR',
        status='draft',
        items=[
            CreateInvoiceItemPayload(
                description_raw='x',
                description_normalized='x',
                item_description_raw='',
                quantity=1,
                unit='ks',
                unit_price=10,
                total_price=10,
            )
        ],
        invoice_number='20260004',
    )
    message = _DummyMessage('/cancel')
    state = _DummyState(
        InvoiceStates.waiting_pdf_decision.state,
        {'edit_stage': 'persisted', 'last_invoice_id': invoice_id},
    )

    asyncio.run(cancel_current_state(message=message, state=state, config=config))

    assert state.cleared is True
    assert message.answers == [PERSISTED_EDIT_CANCELLED_MESSAGE]
    assert InvoiceService(config.db_path).get_invoice_by_id(invoice_id) is not None
