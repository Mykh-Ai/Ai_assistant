from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.supplier import (
    ServiceAliasStates,
    cmd_service,
    service_display_name_input,
    service_short_name_input,
)
from bot.services.db import init_db
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str | None = None, user_id: int = 111) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.current_state = None
        self.data: dict = {}
        self.cleared = False

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()
        self.cleared = True

    async def set_state(self, new_state) -> None:
        self.current_state = new_state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return dict(self.data)


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'service.db',
        storage_dir=tmp_path,
    )


def _setup_supplier(db_path: Path, telegram_id: int = 111) -> None:
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


def test_manual_service_command_flow_still_works(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    start_msg = _DummyMessage(text='/service')

    asyncio.run(cmd_service(start_msg, state, config))
    assert state.current_state == ServiceAliasStates.waiting_short_name
    assert 'Pridanie názvu služby (krok 1/2)' in start_msg.answers[-1]

    short_msg = _DummyMessage(text='opravy')
    asyncio.run(service_short_name_input(short_msg, state))
    assert state.current_state == ServiceAliasStates.waiting_display_name
    assert short_msg.answers[-1] == 'Krok 2/2: napíšte plný názov služby, ktorý sa má použiť vo faktúre/PDF.'

    full_msg = _DummyMessage(text='Opravy elektromotorov')
    asyncio.run(service_display_name_input(full_msg, state, config))
    assert state.cleared is True
    assert 'Názov služby bol uložený.' in full_msg.answers[-1]

    supplier = SupplierService(config.db_path).get_by_telegram_id(111)
    assert supplier is not None and supplier.id is not None
    display_name = ServiceAliasService(config.db_path).resolve_service_display_name(supplier.id, 'opravy')
    assert display_name == 'Opravy elektromotorov'
