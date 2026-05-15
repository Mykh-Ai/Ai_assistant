import asyncio
import json
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.invoice import (
    InvoiceStates,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
    process_invoice_service_clarification,
    process_invoice_slot_clarification,
    process_invoice_text,
    semantic_top_level_input,
)
from bot.services.info_help import build_top_level_unknown_guidance
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.semantic_action_resolver import resolve_bounded_confirmation_reply, resolve_semantic_action


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.message_id = 1
        self.update_id = 1
        self.from_user = None
        self.answers: list[str] = []
        self.documents: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def answer_document(self, document, caption: str | None = None) -> None:
        self.documents.append(caption or '')


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False
        self.data: dict = {}
        self.current_state = None

    async def clear(self) -> None:
        self.cleared = True

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, new_state) -> None:
        self.current_state = new_state

    async def get_data(self) -> dict:
        return dict(self.data)

    async def get_state(self):
        return self.current_state


class _DummyDecisionState:
    def __init__(self) -> None:
        self.data = {'last_invoice_id': 999}
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.cleared = True

    async def get_state(self):
        return None


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def _config_with_api_key(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def test_top_level_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='витворить фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='сделай фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'show_existing_invoice',
                'add_contact',
                'add_service_alias',
                'send_invoice',
                'edit_existing_invoice',
                'edit_invoice',
                'unknown',
            ],
            user_input_text='upraviť fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_existing_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'show_existing_invoice',
                'edit_existing_invoice',
                'delete_existing_invoice',
                'unknown',
            ],
            user_input_text='покажи фактуру номер 04',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'show_existing_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pošli fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'send_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pridaj novú službu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'add_service_alias'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'delete_existing_invoice', 'unknown'],
            user_input_text='delete invoice 02',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_existing_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='blabla',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_top_level_semantic_resolver_system_profile_and_accounting_actions() -> None:
    allowed = [
        'start',
        'create_invoice',
        'show_supplier_profile',
        'edit_supplier',
        'show_recent_accounting_documents',
        'add_receipt',
        'unknown',
    ]

    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='почати',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'start'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='môj profil',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'show_supplier_profile'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='upraviť môj profil',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_supplier'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='покажи останні чеки',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'show_recent_accounting_documents'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='додай, будь ласка, чек',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'add_receipt'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='nahrať prijatú faktúru',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'add_receipt'


def test_top_level_semantic_resolver_does_not_expose_reserved_database_delete() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'unknown'],
            user_input_text='Chcem vymazať moju databázu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_receipt_alias_obeys_allowed_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'unknown'],
            user_input_text='додай, будь ласка, чек',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


@pytest.mark.parametrize(
    'user_input',
    [
        '\u0443\u0434\u0430\u043b\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0443 7',
        '\u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0444\u0430\u043a\u0442\u0443\u0440\u0443 \u043d\u043e\u043c\u0435\u0440 10',
        '\u0432\u0438\u0434\u0430\u043b\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0443 11',
        '\u0432\u044b\u043c\u0430\u0436\u044c \u0444\u0430\u043a\u0442\u0443\u0440\u0443 \u0447\u0438\u0441\u043b\u0430 7',
        'vyma\u017e fakturu cislo 10',
        'VIMA\u0160 FAKTURU \u010cISLO 11',
    ],
)
def test_top_level_delete_invoice_stt_variants_beat_create_invoice(user_input: str) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'add_contact',
                'add_service_alias',
                'send_invoice',
                'edit_existing_invoice',
                'delete_existing_invoice',
                'edit_invoice',
                'unknown',
            ],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_existing_invoice'


def test_top_level_delete_invoice_priority_runs_before_llm_when_key_is_configured() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'edit_existing_invoice',
                'delete_existing_invoice',
                'unknown',
            ],
            user_input_text='\u0443\u0434\u0430\u043b\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0443 10',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'delete_existing_invoice'


def test_top_level_polite_add_receipt_uses_bounded_resolver_when_key_is_configured(monkeypatch) -> None:
    _TopLevelActionOpenAIFake.canonical_action = 'add_receipt'
    _TopLevelActionOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _TopLevelActionOpenAIFake)

    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_receipt', 'unknown'],
            user_input_text='додай, будь ласка, чек',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'add_receipt'
    payload = _TopLevelActionOpenAIFake.last_payload
    assert payload is not None
    assert payload['allowed_actions'] == ['add_receipt', 'create_invoice', 'unknown']


def test_invoice_create_not_misrouted_to_add_contact_when_company_mentioned() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre company ZS',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'


def test_process_invoice_text_routes_add_service_alias_to_existing_service_flow(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('pridaj novú službu')
    state = _DummyState()
    calls: list[str] = []

    async def _resolver(**kwargs):
        return 'add_service_alias'

    async def _start_service(**kwargs) -> None:
        calls.append('service_flow')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_add_service_alias_intake', _start_service)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='pridaj novú službu',
        )
    )

    assert calls == ['service_flow']
    assert message.answers == []


def test_process_invoice_text_routes_system_and_profile_actions_to_existing_flows(tmp_path: Path, monkeypatch) -> None:
    routed: list[str] = []

    async def _start(**kwargs) -> None:
        routed.append('start')

    async def _profile(**kwargs) -> None:
        routed.append('profile')

    async def _edit_profile(**kwargs) -> None:
        routed.append('edit_profile')

    async def _recent(**kwargs) -> None:
        routed.append('recent')

    monkeypatch.setattr('bot.handlers.invoice.cmd_start', _start)
    monkeypatch.setattr('bot.handlers.invoice.cmd_moj_profil', _profile)
    monkeypatch.setattr('bot.handlers.invoice.cmd_upravit_profil', _edit_profile)
    monkeypatch.setattr('bot.handlers.invoice.cmd_blocky', _recent)

    for text in ('start', 'môj profil', 'upraviť môj profil', 'posledné bločky'):
        message = _DummyMessage(text)
        state = _DummyState()
        asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text=text))

    assert routed == ['start', 'profile', 'edit_profile', 'recent']


def test_process_invoice_text_passes_domain_context_for_profile_rekvizity(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    routed: list[str] = []

    async def _resolver(**kwargs):
        captured.update(kwargs)
        return 'show_supplier_profile'

    async def _profile(**kwargs) -> None:
        routed.append('profile')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.cmd_moj_profil', _profile)

    asyncio.run(
        process_invoice_text(
            message=_DummyMessage('Мої реквізити'),
            state=_DummyState(),
            config=_config(tmp_path),
            invoice_text='Мої реквізити',
        )
    )

    assert routed == ['profile']
    assert captured['user_input_text'] == 'Мої реквізити'
    profile_hint = captured['action_hints']['show_supplier_profile']['meaning']
    assert 'billing details' in profile_hint
    assert 'fakturačné údaje dodávateľa' in profile_hint
    assert 'firemné údaje' in profile_hint
    assert 'positive_examples' not in captured['action_hints']['show_supplier_profile']
    assert 'edit or change supplier/company/profile/billing details' in captured['action_hints']['show_supplier_profile']['not_this']


def test_active_fsm_top_level_text_is_not_executed_from_generic_router(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    async def _unexpected_process_invoice_text(**kwargs) -> None:
        calls.append(str(kwargs.get('invoice_text')))

    monkeypatch.setattr('bot.handlers.invoice.process_invoice_text', _unexpected_process_invoice_text)
    state = _DummyState()
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(semantic_top_level_input(_DummyMessage('vytvor faktúru'), state, _config(tmp_path)))

    assert calls == []


def test_process_invoice_text_routes_add_receipt_to_existing_upload_flow_without_invoice(tmp_path: Path) -> None:
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates

    config = _config(tmp_path)
    message = _DummyMessage('додай, будь ласка, чек')
    message.from_user = type('_User', (), {'id': 111})()
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text='додай, будь ласка, чек',
        )
    )

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload
    assert 'fotku alebo PDF' in message.answers[-1]
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_process_invoice_text_edit_existing_invoice_by_short_number(tmp_path: Path, monkeypatch) -> None:
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
        items=[CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)],
        invoice_number='20260015',
    )
    message = _DummyMessage('upraviť faktúru 15')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    calls: list[int] = []

    async def _resolver(**kwargs):
        return 'edit_existing_invoice'

    async def _start_edit(**kwargs):
        calls.append(kwargs['invoice_id'])

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_invoice_edit_flow', _start_edit)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert calls == [invoice_id]
    preview = message.answers[0]
    assert 'Číslo faktúry: 20260015' in preview
    assert 'Dátum vystavenia: 2026-04-30' in preview
    assert 'Dátum dodania: 2026-04-30' in preview
    assert 'Dátum splatnosti: 2026-05-14' in preview
    assert 'x' in preview
    assert 'Množstvo: 1 ks × 10.00 EUR = 10.00 EUR' in preview
    assert 'Celkom: 10.00 EUR' in preview


def test_process_invoice_text_show_existing_invoice_is_read_only_and_clears_state(
    tmp_path: Path, monkeypatch
) -> None:
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
    message = _DummyMessage('покажи фактуру 04')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    calls: list[int] = []

    async def _resolver(**kwargs):
        return 'show_existing_invoice'

    async def _start_edit(**kwargs):
        calls.append(kwargs['invoice_id'])

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_invoice_edit_flow', _start_edit)

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert calls == []
    assert state.cleared is True
    assert InvoiceService(config.db_path).get_invoice_by_id(invoice_id) is not None
    assert 'Číslo faktúry: 20260004' in message.answers[0]
    assert 'Celkom: 10.00 EUR' in message.answers[0]


def test_process_invoice_text_delete_existing_invoice_ambiguous_suffix(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    SupplierService(config.db_path).create_or_replace(
        SupplierProfile(telegram_id=111, name='S', ico='1', dic='1', ic_dph='', address='A', iban='SK1', swift='ABCD', email='a@a.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14)
    )
    service = InvoiceService(config.db_path)
    for num in ('20260002', '20261002'):
        service.create_invoice_with_items(
            supplier_telegram_id=111, contact_id=1, issue_date='2026-04-30', delivery_date='2026-04-30', due_date='2026-05-14', due_days=14,
            total_amount=10, currency='EUR', status='draft',
            items=[CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)],
            invoice_number=num,
        )
    message = _DummyMessage('vymazať faktúru 2')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()

    async def _resolver(**kwargs):
        return 'delete_existing_invoice'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert message.answers[-1] == 'Našiel som viac faktúr. Napíšte viac posledných číslic alebo celé číslo faktúry.'


def test_process_invoice_text_edit_existing_invoice_ambiguity_and_supplier_scope(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = InvoiceService(config.db_path)
    SupplierService(config.db_path).create_or_replace(SupplierProfile(telegram_id=111, name='S1', ico='1', dic='1', ic_dph='', address='A', iban='SK1', swift='ABCD', email='a@a.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14))
    SupplierService(config.db_path).create_or_replace(SupplierProfile(telegram_id=222, name='S2', ico='2', dic='2', ic_dph='', address='B', iban='SK2', swift='EFGH', email='b@b.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14))
    item = CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)
    common = dict(contact_id=1, issue_date='2026-04-30', delivery_date='2026-04-30', due_date='2026-05-14', due_days=14, total_amount=10, currency='EUR', status='draft', items=[item])
    service.create_invoice_with_items(supplier_telegram_id=111, invoice_number='20250015', **common)
    service.create_invoice_with_items(supplier_telegram_id=111, invoice_number='20260015', **common)
    service.create_invoice_with_items(supplier_telegram_id=222, invoice_number='20270015', **common)
    message = _DummyMessage('upraviť faktúru 15')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    async def _resolver(**kwargs):
        return 'edit_existing_invoice'
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert message.answers[-1] == 'Našiel som viac faktúr. Napíšte celé číslo faktúry.'


def test_edit_existing_invoice_missing_pdf_does_not_fail(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = InvoiceService(config.db_path)
    SupplierService(config.db_path).create_or_replace(SupplierProfile(telegram_id=111, name='S1', ico='1', dic='1', ic_dph='', address='A', iban='SK1', swift='ABCD', email='a@a.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14))
    item = CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)
    invoice_id = service.create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        issue_date='2026-04-30',
        delivery_date='2026-04-30',
        due_date='2026-05-14',
        due_days=14,
        total_amount=10,
        currency='EUR',
        status='draft',
        items=[item],
        invoice_number='20260015',
    )
    service.save_pdf_path(invoice_id, str(tmp_path / 'missing.pdf'))
    message = _DummyMessage('upraviť faktúru 15')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    called: list[int] = []
    async def _resolver(**kwargs):
        return 'edit_existing_invoice'
    async def _start_edit(**kwargs):
        called.append(kwargs['invoice_id'])
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_invoice_edit_flow', _start_edit)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert called == [invoice_id]
    assert message.documents == []


def test_state_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='potvrdzujem',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='cancel',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'nie'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_postpdf_decision',
            allowed_actions=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='подтвердить',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


def test_bounded_confirmation_resolver_maps_known_stt_ano_noise() -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='delete_existing_invoice_confirm',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


def test_bounded_confirmation_resolver_positive_regressions() -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='áno',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='нет',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'nie'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='schváliť',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('Так.', 'ano'),
        ('Да.', 'ano'),
        ('Ні.', 'nie'),
        ('Нет.', 'nie'),
        ('Ah, não.', 'ano'),
        ('Ah, não!', 'ano'),
    ],
)
def test_preview_bounded_confirmation_multilingual_and_noisy_inputs(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('schváliť', 'schvalit'),
        ('upraviť', 'upravit'),
        ('zrušiť', 'zrusit'),
        ('Удалить.', 'zrusit'),
        ('delete', 'unknown'),
        ('отменить', 'zrusit'),
        ('зрушити', 'zrusit'),
        ('зрушить', 'zrusit'),
    ],
)
def test_postpdf_bounded_confirmation_multilingual_synonyms(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    'user_input',
    [
        'Добре уложити зміни, зберегти.',
        'Нічого не треба редагувати. Я хочу, щоб ти зберіг те, що ми вже змінили.',
        'сохрани изменения',
        'uložiť zmeny',
        'uloz zmeny',
        'save changes',
    ],
)
def test_postpdf_save_changes_markers_are_approved_locally(user_input: str) -> None:
    diagnostics: dict[str, str | bool | None] = {}

    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    ) == 'schvalit'
    assert diagnostics['fallback_used'] is True
    assert diagnostics['fallback_output'] == 'schvalit'


def test_postpdf_save_marker_cannot_be_overridden_by_llm(monkeypatch) -> None:
    calls: list[str] = []

    class _WrongSaveOpenAIFake:
        def __init__(self, *, api_key: str) -> None:
            calls.append(api_key)
            self.chat = type('_Chat', (), {'completions': self})()

        async def create(self, **kwargs):
            return _FakeResponse('{"canonical":"upravit"}')

    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _WrongSaveOpenAIFake)
    diagnostics: dict[str, str | bool | None] = {}

    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='Добре уложити зміни, зберегти.',
            api_key='sk-test',
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    ) == 'schvalit'
    assert calls == []
    assert diagnostics['fallback_used'] is True
    assert diagnostics['fallback_output'] == 'schvalit'


@pytest.mark.parametrize(
    'user_input',
    [
        'збережи або відредагуй',
        'uloz alebo uprav',
        'save or cancel',
    ],
)
def test_postpdf_conflicting_local_markers_are_unknown(user_input: str) -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type('_Msg', (), {'content': content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _BoundedResolverOpenAIFake:
    last_messages: list[dict] | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _BoundedResolverOpenAIFake.last_messages = kwargs['messages']
        payload = json.loads(kwargs['messages'][1]['content'])
        text = payload['user_input_text']
        reply_type = payload['expected_reply_type']
        normalized = text.lower().strip()

        if reply_type == 'yes_no_confirmation':
            if normalized in {'ano', 'áno', 'так.', 'да.', 'tak.', 'yes.', 'а-а-а-но'}:
                return _FakeResponse('{"canonical":"ano"}')
            if normalized in {'nie', 'ні.', 'нет.', 'неа.', 'не.'}:
                return _FakeResponse('{"canonical":"nie"}')
            return _FakeResponse('{"canonical":"unknown"}')

        if reply_type == 'postpdf_decision':
            if normalized in {'schváliť', 'подтвердить', 'save it'}:
                return _FakeResponse('{"canonical":"schvalit"}')
            if normalized in {'upraviť', 'исправить', 'change invoice'}:
                return _FakeResponse('{"canonical":"upravit"}')
            if normalized in {
                'zrušiť',
                'видалити фактуру',
                'удалить',
                'выдалить',
                'выдалите фактуру',
                'cancel invoice',
                'remove invoice draft',
                'discard this invoice',
            }:
                return _FakeResponse('{"canonical":"zrusit"}')
            return _FakeResponse('{"canonical":"unknown"}')

        return _FakeResponse('{"canonical":"unknown"}')


class _TopLevelActionOpenAIFake:
    last_payload: dict | None = None
    last_system_prompt: str | None = None
    canonical_action = 'show_recent_accounting_documents'

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _TopLevelActionOpenAIFake.last_system_prompt = kwargs['messages'][0]['content']
        _TopLevelActionOpenAIFake.last_payload = json.loads(kwargs['messages'][1]['content'])
        return _FakeResponse(json.dumps({'canonical_action': _TopLevelActionOpenAIFake.canonical_action}))


class _InventedTopLevelActionOpenAIFake:
    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        return _FakeResponse('{"canonical_action":"delete_user_database"}')


def test_top_level_natural_phrase_uses_bounded_resolver_payload(monkeypatch) -> None:
    _TopLevelActionOpenAIFake.canonical_action = 'show_recent_accounting_documents'
    _TopLevelActionOpenAIFake.last_payload = None
    _TopLevelActionOpenAIFake.last_system_prompt = None
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _TopLevelActionOpenAIFake)

    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['show_recent_accounting_documents', 'add_receipt', 'unknown'],
            user_input_text='prosím zobraz mi posledné doklady z nákupov',
            api_key='sk-test',
            model='gpt-4o',
            action_hints={
                'show_recent_accounting_documents': {
                    'meaning': 'view recent confirmed accounting documents',
                    'not_this': ['upload a new receipt'],
                },
            },
        )
    )

    assert result == 'show_recent_accounting_documents'
    payload = _TopLevelActionOpenAIFake.last_payload
    assert payload is not None
    assert payload['allowed_actions'] == ['add_receipt', 'show_recent_accounting_documents', 'unknown']
    assert payload['expected_output'] == {'canonical_action': 'one allowed token or unknown'}
    assert 'show_recent_accounting_documents' in payload['action_hints']
    assert 'internally normalize it to Slovak FakturaBot product semantics' in (
        _TopLevelActionOpenAIFake.last_system_prompt or ''
    )


def test_top_level_profile_rekvizity_uses_llm_slovak_domain_normalization(monkeypatch) -> None:
    _TopLevelActionOpenAIFake.canonical_action = 'show_supplier_profile'
    _TopLevelActionOpenAIFake.last_payload = None
    _TopLevelActionOpenAIFake.last_system_prompt = None
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _TopLevelActionOpenAIFake)

    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['show_supplier_profile', 'edit_supplier', 'unknown'],
            user_input_text='Мої реквізити',
            api_key='sk-test',
            model='gpt-4o',
            action_hints={
                'show_supplier_profile': {
                    'meaning': (
                        'view supplier/company profile data used on invoices in Slovak FakturaBot context: '
                        'fakturačné údaje dodávateľa, firemné údaje, business identifiers, bank/payment details'
                    ),
                    'not_this': ['edit or change those details'],
                },
                'edit_supplier': {
                    'meaning': 'change supplier/company profile data or billing details',
                    'not_this': ['view profile summary only'],
                },
            },
        )
    )

    assert result == 'show_supplier_profile'
    payload = _TopLevelActionOpenAIFake.last_payload
    assert payload is not None
    assert payload['user_input_text'] == 'Мої реквізити'
    assert 'fakturačné údaje dodávateľa' in payload['action_hints']['show_supplier_profile']['meaning']
    assert 'internally normalize it to Slovak FakturaBot product semantics' in (
        _TopLevelActionOpenAIFake.last_system_prompt or ''
    )


def test_top_level_bounded_resolver_rejects_invented_action(monkeypatch) -> None:
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _InventedTopLevelActionOpenAIFake)

    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['show_recent_accounting_documents', 'add_receipt', 'unknown'],
            user_input_text='prosím urob niečo nejasné',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'unknown'


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('ano', 'ano'),
        ('áno', 'ano'),
        ('Так.', 'ano'),
        ('Да.', 'ano'),
        ('Tak.', 'ano'),
        ('Yes.', 'ano'),
        ('А-а-а-но', 'ano'),
        ('nie', 'nie'),
        ('Ні.', 'nie'),
        ('Нет.', 'nie'),
        ('Неа.', 'nie'),
        ('Не.', 'nie'),
        ('... ??', 'unknown'),
    ],
)
def test_preview_confirmation_llm_contract_handles_multilingual_intent(monkeypatch, user_input: str, expected: str) -> None:
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _BoundedResolverOpenAIFake)

    diagnostics: dict[str, str | bool | None] = {}
    result = asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text=user_input,
            api_key='sk-test',
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    )

    assert result == expected
    if diagnostics['fallback_used']:
        assert diagnostics['fallback_output'] == expected
        return
    system_prompt = _BoundedResolverOpenAIFake.last_messages[0]['content']
    user_payload = json.loads(_BoundedResolverOpenAIFake.last_messages[1]['content'])
    assert 'bounded intent normalizer' in system_prompt
    assert 'user is NOT required to say exact "ano"/"nie"' in system_prompt
    assert user_payload['normalization_contract']['mode'] == 'semantic_intent_first'


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('schváliť', 'schvalit'),
        ('подтвердить', 'schvalit'),
        ('save it', 'schvalit'),
        ('upraviť', 'upravit'),
        ('исправить', 'upravit'),
        ('change invoice', 'upravit'),
        ('zrušiť', 'zrusit'),
        ('видалити фактуру', 'zrusit'),
        ('удалить', 'zrusit'),
        ('Выдалить', 'zrusit'),
        ('Выдалите фактуру', 'zrusit'),
        ('cancel invoice', 'zrusit'),
        ('remove invoice draft', 'zrusit'),
        ('discard this invoice', 'zrusit'),
        ('random noise', 'unknown'),
    ],
)
def test_postpdf_confirmation_llm_contract_normalizes_delete_intent(monkeypatch, user_input: str, expected: str) -> None:
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _BoundedResolverOpenAIFake)

    diagnostics: dict[str, str | bool | None] = {}
    result = asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key='sk-test',
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    )

    assert result == expected
    if diagnostics['fallback_used']:
        assert diagnostics['fallback_output'] == expected
        return
    system_prompt = _BoundedResolverOpenAIFake.last_messages[0]['content']
    user_payload = json.loads(_BoundedResolverOpenAIFake.last_messages[1]['content'])
    assert 'delete/cancel/remove/discard invoice-draft intent to zrusit' in system_prompt
    assert user_payload['normalization_contract']['context_rules']['postpdf_decision'][
        'delete_cancel_remove_discard_invoice_draft'
    ] == 'zrusit_if_allowed'


def test_unknown_top_level_gets_info_help_guidance(tmp_path: Path) -> None:
    message = _DummyMessage('blabla')
    state = _DummyState()
    asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text='blabla'))
    assert state.cleared is True
    assert 'Nerozumiem, čo chcete spraviť.' in message.answers[-1]
    assert 'vytvoriť faktúru' in message.answers[-1]
    assert 'pridaj bloček' in message.answers[-1]


def test_known_reserved_top_level_action_does_not_call_info_help(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('pošli faktúru 20260001')
    state = _DummyState()
    calls: list[str | None] = []

    async def _resolver(**kwargs):
        return 'send_invoice'

    def _info_help(**kwargs) -> str:
        calls.append(kwargs.get('user_input_text'))
        return 'unexpected'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.build_top_level_unknown_guidance', _info_help)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='pošli faktúru 20260001',
        )
    )

    assert calls == []
    assert state.cleared is True
    assert 'Nerozumiem požadovanej akcii' in message.answers[-1]


def test_active_fsm_top_level_text_does_not_route_to_info_help(tmp_path: Path, monkeypatch) -> None:
    calls: list[str | None] = []

    def _info_help(**kwargs) -> str:
        calls.append(kwargs.get('user_input_text'))
        return 'unexpected'

    monkeypatch.setattr('bot.handlers.invoice.build_top_level_unknown_guidance', _info_help)
    state = _DummyState()
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(semantic_top_level_input(_DummyMessage('blabla'), state, _config(tmp_path)))

    assert calls == []


def test_info_help_guidance_builder_has_no_side_effects() -> None:
    first = build_top_level_unknown_guidance(user_input_text='blabla')
    second = build_top_level_unknown_guidance(user_input_text='niečo iné')

    assert first == second
    assert 'Nerozumiem, čo chcete spraviť.' in first
    assert 'vytvoriť faktúru' in first


def test_process_invoice_text_keeps_partial_draft_when_only_service_slot_is_unknown(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        partial_payload = {
            'vstup': {'povodny_text': 'faktura pre Tech Company 150 EUR', 'zisteny_jazyk': 'sk'},
            'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.9},
            'biznis_sk': {
                'odberatel_kandidat': 'Tech Company',
                'polozka_povodna': 'оправы',
                'termin_sluzby_sk': 'неясно',
                'mnozstvo': 1,
                'jednotka': 'ks',
                'suma': 150,
                'cena_za_jednotku': 150,
                'mena': 'EUR',
                'datum_dodania': None,
                'splatnost_dni': 14,
                'datum_splatnosti': None,
            },
            'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
        }
        raise LlmInvoicePayloadError(
            'service unresolved',
            error_code='service_term_unresolved',
            partial_payload=partial_payload,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is False
    assert state.current_state == InvoiceStates.waiting_service_clarification
    assert 'invoice_partial_draft' in state.data
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť typ služby. Spresnite ho, prosím.'


def test_process_invoice_text_keeps_partial_draft_when_customer_slot_is_unknown(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        partial_payload = {
            'vstup': {'povodny_text': 'faktura za opravu 150 EUR', 'zisteny_jazyk': 'sk'},
            'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.9},
            'biznis_sk': {
                'odberatel_kandidat': 'pre firmu',
                'polozka_povodna': 'oprava',
                'termin_sluzby_sk': 'oprava',
                'mnozstvo': 1,
                'jednotka': 'ks',
                'suma': 150,
                'cena_za_jednotku': 150,
                'mena': 'EUR',
                'datum_dodania': '2026-04-12',
                'splatnost_dni': 14,
                'datum_splatnosti': None,
            },
            'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
        }
        raise LlmInvoicePayloadError(
            'customer unresolved',
            error_code='customer_unresolved',
            partial_payload=partial_payload,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is False
    assert state.current_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'customer_name'
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť odberateľa. Spresnite názov firmy, prosím.'


def test_service_clarification_continues_to_preview_without_restart(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('oprava')
    message.from_user = type('User', (), {'id': 777})()
    state = _DummyState()
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    SupplierService(db_path).create_or_replace(
        SupplierProfile(
            telegram_id=777,
            name='Dodavatel SK',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Bratislava 1',
            iban='SK3112000000198742637541',
            swift='TATRSKBX',
            email='supplier@example.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    supplier = SupplierService(db_path).get_by_telegram_id(777)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(
        int(supplier.id),
        service_short_name='oprava',
        service_display_name='Servis a oprava zariadenia',
    )
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-1',
        'raw_text': 'faktura pre Tech Company 150 EUR',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'оправы',
            'service_term_sk': 'неясно',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': None,
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_service_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='oprava',
        )
    )

    assert captured['parsed_draft']['service_term_sk'] == 'oprava'
    assert captured['parsed_draft']['item_name_raw'] == 'oprava'
    assert captured['raw_text'] == 'faktura pre Tech Company 150 EUR'


def test_slot_clarification_applies_delivery_date_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('13.04.2026')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-2',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'delivery_date',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': None,
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='13.04.2026',
        )
    )

    assert captured['parsed_draft']['delivery_date'] == '2026-04-13'


def test_slot_clarification_applies_due_days_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('21')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-3',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'due_days',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': None,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='21',
        )
    )

    assert captured['parsed_draft']['due_days'] == 21


def test_slot_clarification_applies_unit_price_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('250')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-4',
        'raw_text': 'faktura pre Tech Company oprava 2x',
        'unresolved_slot': 'unit_price',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 2,
            'unit': 'ks',
            'amount': None,
            'unit_price': None,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='250',
        )
    )

    assert captured['parsed_draft']['unit_price'] == 250.0


@pytest.mark.parametrize(
    'clarification_text,expected_quantity,expected_unit_price',
    [
        ('3 1500', 3.0, 1500.0),
        ('3 * 1500', 3.0, 1500.0),
        ('3 po 1500', 3.0, 1500.0),
        ('три kusy по 1500', 3.0, 1500.0),
        ('množstvo 3, cena za kus 1500', 3.0, 1500.0),
        ('количество 3, цена 1500', 3.0, 1500.0),
        ('2 крат по 1500', 2.0, 1500.0),
        ('два крат по 1500', 2.0, 1500.0),
        ('dva krát po 1500', 2.0, 1500.0),
        ('1500', 1.0, 1500.0),
        ('3000', 1.0, 3000.0),
    ],
)
def test_slot_clarification_applies_quantity_unit_price_pair_and_continues_to_preview(
    tmp_path: Path, monkeypatch, clarification_text: str, expected_quantity: float, expected_unit_price: float
) -> None:
    message = _DummyMessage(clarification_text)
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-qp',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'quantity_unit_price_pair',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': None,
            'unit': 'ks',
            'amount': None,
            'unit_price': None,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text=clarification_text,
        )
    )

    assert captured['parsed_draft']['quantity'] == expected_quantity
    assert captured['parsed_draft']['unit_price'] == expected_unit_price


def test_process_invoice_text_fails_loudly_on_fatal_payload_error(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        raise LlmInvoicePayloadError('fatal shape issue', error_code='fatal_payload')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is True
    assert message.answers[-1] == 'AI návrh faktúry bol neplatný. Skúste vstup poslať znova.'


def test_preview_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('maybe')
    state = _DummyState()
    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=_config(tmp_path),
            confirmation_text='maybe',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'


def test_postpdf_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('later')
    state = _DummyDecisionState()
    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=_config(tmp_path),
            decision_text='later',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'
