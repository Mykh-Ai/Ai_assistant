from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.onboarding import OnboardingStates, onboarding_confirm, onboarding_email
from bot.services.db import init_db
from bot.services.invoice_service import InvoiceService
from bot.services.supplier_service import SupplierService


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str, user_id: int = 111) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.current_state = OnboardingStates.confirm
        self.data = {
            'name': 'Dodavatel',
            'ico': '12345678',
            'dic': '1234567890',
            'ic_dph': '',
            'address': 'Bratislava',
            'iban': 'SK3112000000198742637541',
            'swift': 'TATRSKBX',
            'email': 'supplier@example.com',
            'smtp_host': None,
            'smtp_user': None,
            'smtp_pass': None,
            'invoice_number_issue_year': 2026,
            'first_invoice_number': '20260025',
            'days_due': '14',
        }

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'onboarding.db',
        storage_dir=tmp_path,
    )


def test_onboarding_confirm_accepts_shared_yes_alias(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('ok')
    state = _DummyState()

    asyncio.run(onboarding_confirm(message, state, config))

    saved = SupplierService(config.db_path).get_by_telegram_id(111)
    assert saved is not None
    assert saved.name == 'Dodavatel'
    assert saved.smtp_host is None
    assert saved.smtp_user is None
    assert saved.smtp_pass is None
    assert InvoiceService(config.db_path).get_first_invoice_number(
        supplier_telegram_id=111,
        issue_year=2026,
    ) == '20260025'
    assert state.current_state is None


def test_onboarding_confirm_accepts_shared_no_alias(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('no')
    state = _DummyState()

    asyncio.run(onboarding_confirm(message, state, config))

    assert SupplierService(config.db_path).get_by_telegram_id(111) is None
    assert state.current_state is None
    assert message.answers[-1] == 'Onboarding bol zrušený. Pre nový pokus spustite /supplier.'
