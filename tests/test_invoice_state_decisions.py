from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from unittest.mock import patch

from bot.config import Config
from bot.handlers.invoice import (
    InvoiceStates,
    _format_preview,
    _invoice_exact_value_recovery_hint,
    _resolve_invoice_edit_scope,
    invoice_edit_invoice_action,
    invoice_edit_invoice_date_value,
    invoice_edit_description_value,
    invoice_edit_invoice_number_value,
    invoice_edit_item_action,
    invoice_edit_item_numeric_value,
    invoice_edit_item_target,
    invoice_edit_scope,
    invoice_edit_service_value,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
    invoice_delete_existing_invoice_confirm,
    invoice_mark_existing_invoice_paid_confirm,
    process_invoice_text,
    start_invoice_edit_flow,
)
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db, managed_connection
from bot.services.invoice_service import CreateInvoiceItemPayload, CreateInvoicePayload, InvoiceService
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, user_id: int, text: str = '') -> None:
        self.from_user = _DummyUser(user_id)
        self.text = text
        self.answers: list[str] = []
        self.documents: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def answer_document(self, document, caption: str | None = None) -> None:
        self.documents.append(caption or '')


class _DummyState:
    def __init__(self, data: dict | None = None) -> None:
        self.data: dict = data or {}
        self.current_state = None
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, new_state) -> None:
        self.current_state = new_state

    async def clear(self) -> None:
        self.cleared = True

    async def get_state(self):
        return self.current_state


def _setup_profiles(db_path: Path, telegram_id: int) -> int:
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
            address='Kosice',
            email='contact@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    contact = ContactService(db_path).get_by_name(telegram_id, 'Tech Company s.r.o.')
    assert contact is not None
    assert contact.id is not None
    return contact.id


def _draft_for_tests(contact_id: int, *, invoice_number: str = '20260009') -> dict:
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
        'invoice_number': invoice_number,
        'invoice_number_manual_override': False,
        'items': [
            {
                'service_short_name': 'servis',
                'service_display_name': 'Servis zariadenia',
                'quantity': 1,
                'unit_price': 100,
                'unit': 'ks',
                'amount': 100,
                'item_description_raw': 'hala A',
            }
        ],
    }


def test_delete_existing_invoice_confirmation_yes_deletes_invoice_items_and_pdf(tmp_path: Path) -> None:
    telegram_id = 9010
    db_path = tmp_path / 'delete.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(bot_token='token', openai_api_key='key', openai_stt_model='whisper-1', openai_llm_model='gpt-4o', debug_invoice_transparency=False, db_path=db_path, storage_dir=tmp_path)
    service = InvoiceService(db_path)
    invoice_id = service.create_invoice_with_items(
        supplier_telegram_id=telegram_id, contact_id=contact_id, issue_date='2026-04-12', delivery_date='2026-04-12', due_date='2026-04-26', due_days=14,
        total_amount=100, currency='EUR', status='pripravena',
        items=[CreateInvoiceItemPayload(description_raw='servis', description_normalized='servis', item_description_raw=None, quantity=1, unit='ks', unit_price=100, total_price=100)],
        invoice_number='20260015',
    )
    pdf_path = tmp_path / 'invoice.pdf'
    pdf_path.write_bytes(b'pdf')
    service.save_pdf_path(invoice_id, str(pdf_path))
    message = _DummyMessage(telegram_id, 'ano')
    state = _DummyState({'pending_delete_invoice_id': invoice_id, 'pending_delete_invoice_number': '20260015', 'pending_delete_pdf_path': str(pdf_path)})
    asyncio.run(invoice_delete_existing_invoice_confirm(message, state, config))
    assert state.cleared is True
    assert service.get_invoice_by_id(invoice_id) is None
    assert not service.get_items_by_invoice_id(invoice_id)
    assert not pdf_path.exists()


def test_delete_existing_invoice_confirmation_no_cancels(tmp_path: Path) -> None:
    message = _DummyMessage(1, 'nie')
    state = _DummyState({'pending_delete_invoice_id': 1, 'pending_delete_invoice_number': '20260001'})
    config = Config(bot_token='token', openai_api_key='key', openai_stt_model='whisper-1', openai_llm_model='gpt-4o', debug_invoice_transparency=False, db_path=tmp_path / 'x.db', storage_dir=tmp_path)
    asyncio.run(invoice_delete_existing_invoice_confirm(message, state, config))
    assert state.cleared is True


def test_delete_existing_invoice_confirmation_uses_delete_context_for_unknown(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage(1, 'mozno')
    state = _DummyState({'pending_delete_invoice_id': 1, 'pending_delete_invoice_number': '20260001'})
    config = Config(bot_token='token', openai_api_key='key', openai_stt_model='whisper-1', openai_llm_model='gpt-4o', debug_invoice_transparency=False, db_path=tmp_path / 'x.db', storage_dir=tmp_path)
    captured: dict[str, str] = {}

    async def _resolver(**kwargs):
        captured['context_name'] = kwargs['context_name']
        return 'unknown'

    monkeypatch.setattr('bot.handlers.invoice.resolve_yes_no', _resolver)
    asyncio.run(invoice_delete_existing_invoice_confirm(message, state, config))

    assert captured['context_name'] == 'delete_existing_invoice_confirm'
    assert state.cleared is False
    assert 'odpovedzte' in message.answers[-1]
    assert 'Ak nechcete faktúru vymazať, napíšte „nie“ alebo „zrušiť“.' in message.answers[-1]


def test_preview_contains_proposed_invoice_number() -> None:
    preview = _format_preview(
        None,
        {
            'customer_name': 'Tech Company s.r.o.',
            'service_short_name': 'servis',
            'service_display_name': 'Servis zariadenia',
            'quantity': 1,
            'unit_price': 100,
            'unit': 'ks',
            'amount': 100,
            'currency': 'EUR',
            'issue_date': '2026-04-12',
            'delivery_date': '2026-04-12',
            'due_date': '2026-04-26',
            'invoice_number': '20260009',
        },
    )

    assert 'Číslo faktúry: 20260009 (návrh)' in preview
    assert 'schváliť' in preview
    assert 'upraviť' in preview
    assert 'zrušiť' in preview


def test_waiting_confirm_accepts_multilingual_yes_and_generates_pdf(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9001
    db_path = tmp_path / 'state.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF-1.4 fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'invoice_draft': {
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
        }
    )

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='так',
        )
    )

    assert state.cleared is True
    invoice = InvoiceService(db_path).get_invoice_by_number('20260001')
    assert invoice is not None
    assert invoice.status == 'pripravena'
    assert invoice.pdf_path
    assert message.documents
    assert message.answers[-1] == 'Faktúra 20260001 bola vytvorená.'


def test_preview_approval_stores_confirmed_customer_alias(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9101
    db_path = tmp_path / 'preview-alias.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF-1.4 fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    draft = _draft_for_tests(contact_id, invoice_number='20260015')
    draft['customer_alias_candidate'] = 'Realtim Technologies SK'
    draft['customer_resolution_source'] = 'fuzzy_match'
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': draft})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='schvalit',
        )
    )

    with managed_connection(db_path) as connection:
        row = connection.execute(
            (
                'SELECT alias_text, target_id, source '
                'FROM confirmed_semantic_alias '
                'WHERE supplier_telegram_id = ? AND alias_text = ?'
            ),
            (telegram_id, 'Realtim Technologies SK'),
        ).fetchone()

    assert row is not None
    assert row[1] == contact_id
    assert row[2] == 'invoice_preview_approved_fuzzy_match'


def test_preview_approval_stores_confirmed_customer_alias_from_raw_mention(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9103
    db_path = tmp_path / 'preview-raw-alias.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF-1.4 fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    draft = _draft_for_tests(contact_id, invoice_number='20260016')
    draft['customer_alias_candidate'] = 'tek kompani'
    draft['customer_resolution_source'] = 'raw_mention'
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': draft})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='schvalit',
        )
    )

    with managed_connection(db_path) as connection:
        row = connection.execute(
            (
                'SELECT alias_text, target_id, source '
                'FROM confirmed_semantic_alias '
                'WHERE supplier_telegram_id = ? AND alias_text = ?'
            ),
            (telegram_id, 'tek kompani'),
        ).fetchone()

    assert row is not None
    assert row[1] == contact_id
    assert row[2] == 'invoice_preview_approved_raw_mention'


def test_preview_approval_stores_confirmed_service_alias_from_raw_mention(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9104
    db_path = tmp_path / 'preview-service-raw-alias.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    alias_service = ServiceAliasService(db_path)
    alias_service.create_mapping(int(supplier.id), 'servis', 'Servis zariadenia')
    service_mapping = alias_service.get_mapping_by_alias(
        supplier_id=int(supplier.id),
        service_short_name='servis',
    )
    assert service_mapping is not None
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF-1.4 fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    draft = _draft_for_tests(contact_id, invoice_number='20260017')
    draft['items'][0]['service_alias_id'] = service_mapping.id
    draft['items'][0]['service_alias_candidate'] = 'електро сервіс'
    draft['items'][0]['service_resolution_source'] = 'raw_mention'
    manual_alias_count_before = len(alias_service.list_mappings(int(supplier.id)))
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': draft})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='schvalit',
        )
    )

    with managed_connection(db_path) as connection:
        row = connection.execute(
            (
                'SELECT alias_text, target_type, target_id, source '
                'FROM confirmed_semantic_alias '
                'WHERE supplier_telegram_id = ? AND domain = ? AND alias_text = ?'
            ),
            (telegram_id, 'invoice_service', 'електро сервіс'),
        ).fetchone()

    assert row is not None
    assert row[1] == 'supplier_service_alias'
    assert row[2] == service_mapping.id
    assert row[3] == 'invoice_preview_approved_raw_mention'
    assert len(alias_service.list_mappings(int(supplier.id))) == manual_alias_count_before


def test_preview_cancel_does_not_store_service_alias(tmp_path: Path) -> None:
    telegram_id = 9105
    db_path = tmp_path / 'preview-service-alias-cancel.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    alias_service = ServiceAliasService(db_path)
    alias_service.create_mapping(int(supplier.id), 'servis', 'Servis zariadenia')
    service_mapping = alias_service.get_mapping_by_alias(
        supplier_id=int(supplier.id),
        service_short_name='servis',
    )
    assert service_mapping is not None
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    draft = _draft_for_tests(contact_id, invoice_number='20260018')
    draft['items'][0]['service_alias_id'] = service_mapping.id
    draft['items'][0]['service_alias_candidate'] = 'електро сервіс'
    draft['items'][0]['service_resolution_source'] = 'raw_mention'
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': draft})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='zrusit',
        )
    )

    with managed_connection(db_path) as connection:
        count = connection.execute(
            (
                'SELECT COUNT(*) '
                'FROM confirmed_semantic_alias '
                'WHERE supplier_telegram_id = ? AND domain = ?'
            ),
            (telegram_id, 'invoice_service'),
        ).fetchone()[0]

    assert count == 0


def test_preview_cancel_does_not_store_customer_alias(tmp_path: Path) -> None:
    telegram_id = 9102
    db_path = tmp_path / 'preview-alias-cancel.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    draft = _draft_for_tests(contact_id, invoice_number='20260015')
    draft['customer_alias_candidate'] = 'Realtim Technologies SK'
    draft['customer_resolution_source'] = 'fuzzy_match'
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': draft})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='zrusit',
        )
    )

    with managed_connection(db_path) as connection:
        count = connection.execute(
            'SELECT COUNT(*) FROM confirmed_semantic_alias WHERE supplier_telegram_id = ?',
            (telegram_id,),
        ).fetchone()[0]

    assert count == 0


def test_waiting_confirm_accepts_multilingual_no_and_clears_state(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'state.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState()

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='нет',
        )
    )

    assert state.cleared is True
    assert 'Návrh faktúry bol zrušený.' in message.answers[-1]


def test_preview_edit_enters_draft_edit_flow_without_invoice_row(tmp_path: Path) -> None:
    telegram_id = 9003
    db_path = tmp_path / 'draft-edit-entry.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': _draft_for_tests(contact_id)})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='upraviť',
        )
    )

    assert state.current_state == InvoiceStates.waiting_edit_scope
    assert state.data['edit_stage'] == 'draft'
    assert state.data['edit_invoice_id'] is None
    assert InvoiceService(db_path).get_invoice_by_number('20260009') is None
    assert not message.documents


def test_preview_edit_direct_delivery_date_text_skips_scope_loop_and_returns_updated_preview(
    tmp_path: Path,
    monkeypatch,
) -> None:
    telegram_id = 9013
    db_path = tmp_path / 'draft-edit-direct-delivery-date.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': _draft_for_tests(contact_id)})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='upraviť',
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_scope

    captured_inputs: list[str] = []

    async def _resolve_direct_delivery_date(*, user_input_text: str, **kwargs) -> str:
        captured_inputs.append(user_input_text)
        return 'edit_invoice_delivery_date'

    async def _normalize_date(**kwargs) -> str:
        return '15.08.2026'

    monkeypatch.setattr('bot.handlers.invoice._resolve_invoice_edit_scope', _resolve_direct_delivery_date)
    monkeypatch.setattr('bot.handlers.invoice.resolve_invoice_date_normalization', _normalize_date)

    asyncio.run(
        invoice_edit_scope(
            message=type(
                'M',
                (),
                {'from_user': message.from_user, 'text': 'Датом додання', 'answer': message.answer},
            )(),
            state=state,
            config=config,
        )
    )

    assert captured_inputs == ['Датом додання']
    assert state.current_state == InvoiceStates.waiting_edit_invoice_date_value
    assert state.data['edit_invoice_date_operation'] == 'edit_invoice_delivery_date'

    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type(
                'M',
                (),
                {'from_user': message.from_user, 'text': '15 августа', 'answer': message.answer},
            )(),
            state=state,
            config=config,
        )
    )

    assert state.data['invoice_draft']['delivery_date'] == '2026-08-15'
    assert state.current_state == InvoiceStates.waiting_confirm
    assert 'Dátum dodania' in message.answers[-1]
    assert InvoiceService(db_path).get_invoice_by_number('20260009') is None


def test_invoice_edit_entry_resolver_exposes_concrete_actions_to_llm(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    async def _resolver(**kwargs) -> str:
        captured.update(kwargs)
        return 'edit_invoice_delivery_date'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'resolver-contract.db',
        storage_dir=tmp_path,
    )

    result = asyncio.run(
        _resolve_invoice_edit_scope(
            config=config,
            user_input_text='Датом додання',
        )
    )

    assert result == 'edit_invoice_delivery_date'
    assert captured['context_name'] == 'invoice_edit_scope_selection'
    assert 'edit_invoice_delivery_date' in captured['allowed_actions']
    assert 'edit_item_quantity' in captured['allowed_actions']
    assert captured['action_hints']['edit_invoice_delivery_date']['meaning']


def test_edit_scope_direct_clear_item_details_completes_without_extra_submenu(tmp_path: Path) -> None:
    telegram_id = 9016
    db_path = tmp_path / 'draft-edit-direct-clear-details.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    draft = _draft_for_tests(contact_id)
    draft['items'] = [
        {
            'service_short_name': 'servis',
            'service_display_name': 'Servis zariadenia',
            'quantity': 1,
            'unit': 'ks',
            'unit_price': 100,
            'amount': 100,
            'item_description_raw': 'hala B',
        }
    ]
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft})
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(
        invoice_edit_scope(
            message=message,
            state=state,
            config=config,
            canonical_operation='clear_item_details',
        )
    )

    assert state.current_state == InvoiceStates.waiting_confirm
    assert state.data['invoice_draft']['items'][0]['item_description_raw'] is None
    assert message.answers[-1].startswith('Detaily položky boli vymazané.')


def test_edit_scope_direct_operations_cover_every_supported_sublevel(tmp_path: Path) -> None:
    telegram_id = 9014
    db_path = tmp_path / 'draft-edit-direct-operation-matrix.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    cases = {
        'edit_invoice_number': (InvoiceStates.waiting_edit_invoice_number_value, None),
        'edit_invoice_issue_date': (InvoiceStates.waiting_edit_invoice_date_value, 'edit_invoice_issue_date'),
        'edit_invoice_delivery_date': (InvoiceStates.waiting_edit_invoice_date_value, 'edit_invoice_delivery_date'),
        'edit_invoice_due_date': (InvoiceStates.waiting_edit_invoice_date_value, 'edit_invoice_due_date'),
        'replace_service': (InvoiceStates.waiting_edit_service_value, 'replace_service'),
        'replace_main_description': (InvoiceStates.waiting_edit_description_value, 'replace_main_description'),
        'add_item_details': (InvoiceStates.waiting_edit_description_value, 'add_item_details'),
        'edit_item_quantity': (InvoiceStates.waiting_edit_item_numeric_value, 'edit_item_quantity'),
        'edit_item_unit_price': (InvoiceStates.waiting_edit_item_numeric_value, 'edit_item_unit_price'),
        'edit_item_total_amount': (InvoiceStates.waiting_edit_item_numeric_value, 'edit_item_total_amount'),
    }

    for operation, (expected_state, expected_mode) in cases.items():
        draft = _draft_for_tests(contact_id)
        state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft})
        state.current_state = InvoiceStates.waiting_edit_scope
        message = _DummyMessage(telegram_id, text='natural language selection')
        asyncio.run(
            invoice_edit_scope(
                message=message,
                state=state,
                config=config,
                canonical_operation=operation,
            )
        )
        assert state.current_state == expected_state, operation
        if operation.startswith('edit_invoice_') and operation != 'edit_invoice_number':
            assert state.data['edit_invoice_date_operation'] == expected_mode
        if operation in {
            'replace_service',
            'replace_main_description',
            'add_item_details',
            'edit_item_quantity',
            'edit_item_unit_price',
            'edit_item_total_amount',
        }:
            assert state.data['edit_item_action_mode'] == expected_mode


def test_direct_multi_item_operation_asks_only_for_target_then_continues(tmp_path: Path) -> None:
    telegram_id = 9015
    db_path = tmp_path / 'draft-edit-direct-multi-item.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    draft = _draft_for_tests(contact_id)
    draft['items'] = [
        {
            'service_short_name': 'servis',
            'service_display_name': 'Servis zariadenia',
            'quantity': 1,
            'unit': 'ks',
            'unit_price': 100,
            'amount': 100,
            'item_description_raw': None,
        },
        {
            'service_short_name': 'montaz',
            'service_display_name': 'Montáž zariadenia',
            'quantity': 1,
            'unit': 'ks',
            'unit_price': 200,
            'amount': 200,
            'item_description_raw': None,
        },
    ]
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft})
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(
        invoice_edit_scope(
            message=message,
            state=state,
            config=config,
            canonical_operation='edit_item_quantity',
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_item_target
    assert state.data['invoice_edit_pending_item_operation'] == 'edit_item_quantity'

    asyncio.run(
        invoice_edit_item_target(
            message=message,
            state=state,
            config=config,
            canonical_target_index=2,
        )
    )
    assert state.data['edit_target_item_index'] == 2
    assert state.data['edit_item_action_mode'] == 'edit_item_quantity'
    assert state.current_state == InvoiceStates.waiting_edit_item_numeric_value


def test_preview_finalize_rejects_used_proposed_invoice_number(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9004
    db_path = tmp_path / 'draft-number-conflict.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    service = InvoiceService(db_path)
    service.create_invoice_with_items(
        supplier_telegram_id=telegram_id,
        contact_id=contact_id,
        issue_date='2026-04-12',
        delivery_date='2026-04-12',
        due_date='2026-04-26',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='pripravena',
        items=[
            CreateInvoiceItemPayload(
                description_raw='servis',
                description_normalized='servis',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=100,
                total_price=100,
            )
        ],
        invoice_number='20260009',
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'invoice_draft': _draft_for_tests(contact_id)})

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='schváliť',
        )
    )

    assert state.cleared is False
    assert state.current_state == InvoiceStates.waiting_edit_invoice_number_value
    assert 'Číslo faktúry 20260009 už existuje' in message.answers[-1]
    assert not message.documents


def test_draft_invoice_number_edit_updates_proposed_number_and_manual_override(tmp_path: Path) -> None:
    telegram_id = 9005
    db_path = tmp_path / 'draft-number-edit.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': _draft_for_tests(contact_id)})

    message.text = '20260010'
    asyncio.run(invoice_edit_invoice_number_value(message=message, state=state, config=config))

    draft = state.data['invoice_draft']
    assert draft['invoice_number'] == '20260010'
    assert draft['invoice_number_manual_override'] is True
    assert state.current_state == InvoiceStates.waiting_confirm
    assert 'Číslo faktúry: 20260010 (návrh)' in message.answers[-1]
    assert not message.documents


def test_draft_date_edit_updates_fsm_and_rejects_due_date_before_issue(tmp_path: Path) -> None:
    telegram_id = 9006
    db_path = tmp_path / 'draft-date-edit.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'edit_stage': 'draft',
            'invoice_draft': _draft_for_tests(contact_id),
            'edit_invoice_date_operation': 'edit_invoice_delivery_date',
        }
    )

    message.text = '13.04.2026'
    asyncio.run(invoice_edit_invoice_date_value(message=message, state=state, config=config))

    assert state.data['invoice_draft']['delivery_date'] == '2026-04-13'
    assert state.current_state == InvoiceStates.waiting_confirm
    assert 'Dátum dodania' in message.answers[-1]
    assert not message.documents

    due_state = _DummyState(
        data={
            'edit_stage': 'draft',
            'invoice_draft': _draft_for_tests(contact_id),
            'edit_invoice_date_operation': 'edit_invoice_due_date',
        }
    )
    due_message = _DummyMessage(telegram_id)
    due_message.text = '11.04.2026'
    asyncio.run(invoice_edit_invoice_date_value(message=due_message, state=due_state, config=config))

    assert due_state.current_state is None
    assert due_state.data['invoice_draft']['due_date'] == '2026-04-26'
    assert (
        'Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.'
        in due_message.answers[-1]
    )
    assert _invoice_exact_value_recovery_hint() in due_message.answers[-1]


def test_draft_item_edits_mutate_fsm_without_pdf_rebuild(tmp_path: Path) -> None:
    telegram_id = 9007
    db_path = tmp_path / 'draft-item-edit.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(int(supplier.id), 'montaz', 'Montáž zariadenia')
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    state = _DummyState(
        data={'edit_stage': 'draft', 'invoice_draft': _draft_for_tests(contact_id), 'edit_target_item_index': 1}
    )
    service_message = _DummyMessage(telegram_id)
    service_message.text = 'montaz'
    asyncio.run(invoice_edit_service_value(message=service_message, state=state, config=config))
    assert state.data['invoice_draft']['items'][0]['service_short_name'] == 'montaz'
    assert state.data['invoice_draft']['items'][0]['service_display_name'] == 'Montáž zariadenia'
    assert state.current_state == InvoiceStates.waiting_confirm

    state.data.update({'edit_stage': 'draft', 'edit_target_item_index': 1, 'edit_item_action_mode': 'replace_main_description'})
    replace_message = _DummyMessage(telegram_id)
    replace_message.text = 'Nová služba'
    asyncio.run(invoice_edit_description_value(message=replace_message, state=state, config=config))
    assert state.data['invoice_draft']['items'][0]['service_short_name'] == 'Nová služba'

    state.data.update({'edit_stage': 'draft', 'edit_target_item_index': 1, 'edit_item_action_mode': 'add_item_details'})
    add_message = _DummyMessage(telegram_id)
    add_message.text = 'detail B'
    asyncio.run(invoice_edit_description_value(message=add_message, state=state, config=config))
    assert state.data['invoice_draft']['items'][0]['item_description_raw'] == 'hala A; detail B'

    state.data.update({'edit_stage': 'draft', 'edit_target_item_index': 1})
    clear_message = _DummyMessage(telegram_id)
    clear_message.text = 'vymazať detaily položky'
    asyncio.run(invoice_edit_item_action(message=clear_message, state=state, config=config))
    assert state.data['invoice_draft']['items'][0]['item_description_raw'] is None
    assert not service_message.documents
    assert not replace_message.documents
    assert not add_message.documents
    assert not clear_message.documents


def test_waiting_confirm_persists_multiple_items_when_present(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9002
    db_path = tmp_path / 'state_multi.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF-1.4 fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'invoice_draft': {
                'customer_name': 'Tech Company s.r.o.',
                'contact_id': contact_id,
                'service_short_name': 'oprava',
                'service_display_name': 'Servis a oprava zariadenia',
                'quantity': 1,
                'unit_price': 3000,
                'unit': 'ks',
                'amount': 5000,
                'currency': 'EUR',
                'issue_date': '2026-04-12',
                'delivery_date': '2026-04-12',
                'due_days': 14,
                'due_date': '2026-04-26',
                'items': [
                    {
                        'service_short_name': 'oprava',
                        'service_display_name': 'Servis a oprava zariadenia',
                        'quantity': 1,
                        'unit_price': 3000,
                        'unit': 'ks',
                        'amount': 3000,
                    },
                    {
                        'service_short_name': 'montáž',
                        'service_display_name': 'Montáž zariadenia',
                        'quantity': 2,
                        'unit_price': 1000,
                        'unit': 'ks',
                        'amount': 2000,
                    },
                ],
            }
        }
    )

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='ano',
        )
    )

    invoice = InvoiceService(db_path).get_invoice_by_number('20260001')
    assert invoice is not None
    invoice_id = invoice.id
    items = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)
    assert len(items) == 2
    assert items[0].description_raw == 'oprava'
    assert items[1].description_raw == 'montáž'


def test_waiting_confirm_rejects_total_mismatch_for_items(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9003
    db_path = tmp_path / 'state_multi_mismatch.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF-1.4 fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'invoice_draft': {
                'customer_name': 'Tech Company s.r.o.',
                'contact_id': contact_id,
                'service_short_name': 'oprava',
                'service_display_name': 'Servis a oprava zariadenia',
                'quantity': 1,
                'unit_price': 3000,
                'unit': 'ks',
                'amount': 4000,
                'currency': 'EUR',
                'issue_date': '2026-04-12',
                'delivery_date': '2026-04-12',
                'due_days': 14,
                'due_date': '2026-04-26',
                'items': [
                    {'service_short_name': 'oprava', 'service_display_name': 'Servis a oprava zariadenia', 'quantity': 1, 'unit_price': 3000, 'unit': 'ks', 'amount': 3000},
                    {'service_short_name': 'montáž', 'service_display_name': 'Montáž zariadenia', 'quantity': 2, 'unit_price': 1000, 'unit': 'ks', 'amount': 2000},
                ],
            }
        }
    )

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='ano',
        )
    )

    assert state.cleared is True
    assert 'Nepodarilo sa dokončiť vytvorenie PDF faktúry. Skúste to znova.' in message.answers[-1]
    assert InvoiceService(db_path).get_invoice_by_number('20260001') is None


def test_waiting_confirm_stt_ano_noise_approves_and_reports_missing_draft(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'state.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState()

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='Ah, não.',
        )
    )

    assert state.cleared is True
    assert 'Spustite /invoice znova.' in message.answers[-1]


def test_waiting_confirm_stt_ano_noise_with_exclamation_approves_and_reports_missing_draft(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'state.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState()

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='Ah, não!',
        )
    )

    assert state.cleared is True
    assert 'Spustite /invoice znova.' in message.answers[-1]


def test_waiting_confirm_logs_resolver_and_branch_observability(tmp_path: Path, monkeypatch, caplog) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=True,
        db_path=tmp_path / 'state.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState()
    state.current_state = InvoiceStates.waiting_confirm.state

    async def _resolver(**kwargs):
        diagnostics = kwargs.get('diagnostics')
        if diagnostics is not None:
            diagnostics['raw_model_output'] = '{"canonical":"unknown"}'
            diagnostics['normalized_output'] = 'unknown'
            diagnostics['fallback_used'] = False
            diagnostics['fallback_output'] = None
        return 'unknown'

    monkeypatch.setattr('bot.handlers.invoice.resolve_bounded_confirmation_reply', _resolver)

    with caplog.at_level(logging.INFO):
        asyncio.run(
            process_invoice_preview_confirmation(
                message=message,
                state=state,
                config=config,
                confirmation_text='random text',
            )
        )

    assert any('"event": "confirm_resolver_request"' in rec.message for rec in caplog.records)
    assert any('"event": "confirm_resolver_response"' in rec.message for rec in caplog.records)
    assert any('"event": "confirm_unknown_contract_gap"' in rec.message for rec in caplog.records)
    assert any('"event": "confirm_branch_decision"' in rec.message for rec in caplog.records)


def _create_invoice_with_pdf(db_path: Path, pdf_path: Path, supplier_telegram_id: int = 1) -> int:
    service = InvoiceService(db_path)
    invoice_id = service.create_invoice_with_one_item(
        CreateInvoicePayload(
            supplier_telegram_id=supplier_telegram_id,
            contact_id=1,
            issue_date='2026-04-12',
            delivery_date='2026-04-12',
            due_date='2026-04-26',
            due_days=14,
            total_amount=200.0,
            currency='EUR',
            status='draft_pdf_ready',
            item_description_raw='servis',
            item_description_normalized='Servis',
            item_quantity=1.0,
            item_unit='ks',
            item_unit_price=200.0,
            item_total_price=200.0,
        )
    )
    service.save_pdf_path(invoice_id, str(pdf_path))
    pdf_path.write_bytes(b'fake pdf')
    return invoice_id


def _create_editable_invoice(
    *,
    db_path: Path,
    storage_dir: Path,
    telegram_id: int,
    service_short_name: str,
    service_display_name: str,
    item_description_raw: str | None,
) -> int:
    contact_id = _setup_profiles(db_path, telegram_id)
    service = InvoiceService(db_path)
    invoice_id = service.create_invoice_with_one_item(
        CreateInvoicePayload(
            supplier_telegram_id=telegram_id,
            contact_id=contact_id,
            issue_date='2026-04-12',
            delivery_date='2026-04-12',
            due_date='2026-04-26',
            due_days=14,
            total_amount=200.0,
            currency='EUR',
            status='draft_pdf_ready',
            item_description_raw=service_short_name,
            item_description_normalized=service_display_name,
            item_quantity=1.0,
            item_unit='ks',
            item_unit_price=200.0,
            item_total_price=200.0,
        )
    )
    item = service.get_items_by_invoice_id(invoice_id)[0]
    service.update_item_description(item_id=item.id, item_description_raw=item_description_raw)
    invoice = service.get_invoice_by_id(invoice_id)
    assert invoice is not None
    pdf_path = storage_dir / f'{invoice.invoice_number}.pdf'
    pdf_path.write_bytes(b'fake pdf')
    service.save_pdf_path(invoice_id, str(pdf_path))
    return invoice_id


def test_waiting_pdf_decision_approve_keeps_invoice_and_pdf(tmp_path: Path) -> None:
    db_path = tmp_path / 'approve.db'
    init_db(db_path)
    invoice_id = _create_invoice_with_pdf(db_path, tmp_path / 'approve.pdf')
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(tmp_path / 'approve.pdf')})

    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=config,
            decision_text='schváliť',
        )
    )

    invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert invoice is not None
    assert invoice.status == 'pripravena'
    assert (tmp_path / 'approve.pdf').exists()


def test_waiting_pdf_decision_edit_starts_item_edit_subflow_and_cancel_still_cleans_up(tmp_path: Path) -> None:
    db_path = tmp_path / 'cleanup.db'
    init_db(db_path)
    telegram_id = 777
    _setup_profiles(db_path, telegram_id)
    edit_pdf_path = tmp_path / 'edit.pdf'
    cancel_pdf_path = tmp_path / 'cancel.pdf'
    edit_invoice_id = _create_invoice_with_pdf(db_path, edit_pdf_path, supplier_telegram_id=telegram_id)
    cancel_invoice_id = _create_invoice_with_pdf(db_path, cancel_pdf_path, supplier_telegram_id=telegram_id)
    service = InvoiceService(db_path)
    edit_invoice = service.get_invoice_by_id(edit_invoice_id)
    cancel_invoice = service.get_invoice_by_id(cancel_invoice_id)
    assert edit_invoice is not None
    assert cancel_invoice is not None
    edit_number = edit_invoice.invoice_number
    cancel_number = cancel_invoice.invoice_number

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    edit_state = _DummyState(data={'last_invoice_id': edit_invoice_id, 'last_pdf_path': str(edit_pdf_path)})

    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=edit_state,
            config=config,
            decision_text='upraviť',
        )
    )
    assert service.get_invoice_by_id(edit_invoice_id) is not None
    assert service.get_invoice_by_number(edit_number) is not None
    assert edit_state.current_state == InvoiceStates.waiting_edit_scope
    assert 'Vyberte rozsah úpravy' in message.answers[-1]

    cancel_state = _DummyState(data={'last_invoice_id': cancel_invoice_id, 'last_pdf_path': str(cancel_pdf_path)})
    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=cancel_state,
            config=config,
            decision_text='нет',
        )
    )
    assert not cancel_pdf_path.exists()
    assert service.get_invoice_by_id(cancel_invoice_id) is None
    assert service.get_invoice_by_number(cancel_number) is None


def test_replace_service_keeps_existing_item_description_and_rebuilds_pdf(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 501
    db_path = tmp_path / 'replace-service.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='hala B',
    )
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(int(supplier.id), 'montaz', 'Montáž zariadenia')

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF edited')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(tmp_path / 'old.pdf')})
    asyncio.run(process_invoice_postpdf_decision(message=message, state=state, config=config, decision_text='upraviť'))
    asyncio.run(invoice_edit_scope(message=type('M', (), {'from_user': message.from_user, 'text': 'položka', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_item_action(message=type('M', (), {'from_user': message.from_user, 'text': 'zmeniť službu', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_service_value
    asyncio.run(invoice_edit_service_value(message=type('M', (), {'from_user': message.from_user, 'text': 'montaz', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))

    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.description_raw == 'montaz'
    assert item.description_normalized == 'Montáž zariadenia'
    assert item.item_description_raw == 'hala B'
    assert message.documents
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.answers[-1] == 'Služba položky bola zmenená. Napíšte: schváliť, upraviť alebo zrušiť.'


def test_set_replace_and_clear_item_description_preserve_service_and_rebuild_pdf(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 502
    db_path = tmp_path / 'edit-description.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF edited')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(tmp_path / 'old.pdf')})
    asyncio.run(process_invoice_postpdf_decision(message=message, state=state, config=config, decision_text='upraviť'))
    asyncio.run(invoice_edit_scope(message=type('M', (), {'from_user': message.from_user, 'text': 'položka', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_item_action(message=type('M', (), {'from_user': message.from_user, 'text': 'pridať detaily k položke', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_description_value

    # add details
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'from_user': message.from_user, 'text': 'práce v hale A', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw == 'práce v hale A'
    assert item.description_normalized == 'Servis zariadenia'
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.answers[-1] == 'Detaily položky boli doplnené. Napíšte: schváliť, upraviť alebo zrušiť.'

    # append details
    state.data['last_invoice_id'] = invoice_id
    state.data['edit_invoice_id'] = invoice_id
    state.data['edit_target_item_id'] = item.id
    state.data['edit_item_action_mode'] = 'add_item_details'
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'from_user': message.from_user, 'text': 'práce v hale B', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw == 'práce v hale A; práce v hale B'

    # replace main description
    state.data['edit_item_action_mode'] = 'replace_main_description'
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'from_user': message.from_user, 'text': 'Nový hlavný opis', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.description_raw == 'Nový hlavný opis'
    assert item.description_normalized == 'Nový hlavný opis'


def test_novy_opis_updates_only_invoice_item_without_alias_db_side_effects(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 512
    db_path = tmp_path / 'novy-opis-isolated.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='existujúce detaily',
    )

    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    alias_service = ServiceAliasService(db_path)
    alias_service.create_mapping(int(supplier.id), 'servis', 'Servis zariadenia')
    alias_service.create_mapping(int(supplier.id), 'montaz', 'Montáž zariadenia')
    aliases_before = alias_service.list_mappings(int(supplier.id))

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF edited')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    state = _DummyState(
        data={
            'last_invoice_id': invoice_id,
            'edit_invoice_id': invoice_id,
            'edit_target_item_id': item.id,
            'edit_item_action_mode': 'replace_main_description',
        }
    )
    asyncio.run(
        invoice_edit_description_value(
            message=type(
                'M',
                (),
                {'text': 'Nový hlavný opis', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user},
            )(),
            state=state,
            config=config,
        )
    )

    updated_item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert updated_item.description_raw == 'Nový hlavný opis'
    assert updated_item.description_normalized == 'Nový hlavný opis'
    assert updated_item.description_raw.endswith('opis')
    assert updated_item.description_raw == 'Nový hlavný opis'
    assert updated_item.item_description_raw == 'existujúce detaily'

    aliases_after = alias_service.list_mappings(int(supplier.id))
    assert [(a.service_short_name, a.service_display_name) for a in aliases_after] == [
        (a.service_short_name, a.service_display_name) for a in aliases_before
    ]
    assert message.answers[-1] == 'Opis položky bol nahradený novým textom. Napíšte: schváliť, upraviť alebo zrušiť.'


def test_reject_too_long_item_description_returns_bounded_prompt_and_keeps_previous(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 503
    db_path = tmp_path / 'too-long-description.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='pôvodný opis',
    )

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'edit_invoice_id': invoice_id, 'edit_target_item_id': InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0].id})
    long_text = ' '.join(['veľmi'] * 80)
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'from_user': message.from_user, 'text': long_text, 'answer': message.answer})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw == 'pôvodný opis'
    assert 'príliš dlhý' in message.answers[-1]


def test_item_action_phrase_novy_opis_routes_to_description_branch(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_target_item_id': 11})
    asyncio.run(
        invoice_edit_item_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'nový opis položky', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_description_value
    assert state.data.get('edit_item_action_mode') == 'replace_main_description'


def test_item_action_phrase_zmenit_sluzbu_routes_to_service_branch(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_target_item_id': 11})
    asyncio.run(
        invoice_edit_item_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'zmeniť službu', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_service_value


def test_item_action_phrase_upravit_mnozstvo_routes_to_numeric_branch(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_target_item_id': 11})
    asyncio.run(
        invoice_edit_item_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť množstvo', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_item_numeric_value
    assert state.data.get('edit_item_action_mode') == 'edit_item_quantity'


def test_item_action_phrase_upravit_cena_za_mj_routes_to_numeric_branch(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_target_item_id': 11})
    asyncio.run(
        invoice_edit_item_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť cenu za m.j.', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_item_numeric_value
    assert state.data.get('edit_item_action_mode') == 'edit_item_unit_price'


def test_item_action_phrase_upravit_sumu_routes_to_numeric_branch(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_target_item_id': 11})
    asyncio.run(
        invoice_edit_item_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť sumu položky', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_item_numeric_value
    assert state.data.get('edit_item_action_mode') == 'edit_item_total_amount'


def test_item_action_resolver_maps_multilingual_numeric_phrases(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    checks = [
        ('quantity', 'edit_item_quantity'),
        ('ціна за одиницю', 'edit_item_unit_price'),
        ('total', 'edit_item_total_amount'),
    ]
    for phrase, expected_operation in checks:
        state = _DummyState(data={'edit_target_item_id': 11})
        asyncio.run(
            invoice_edit_item_action(
                message=type('M', (), {'from_user': message.from_user, 'text': phrase, 'answer': message.answer})(),
                state=state,
                config=config,
            )
        )
        assert state.current_state == InvoiceStates.waiting_edit_item_numeric_value
        assert state.data.get('edit_item_action_mode') == expected_operation


def test_item_action_phrase_vymazat_detaily_clears_details_immediately(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 777
    db_path = tmp_path / 'clear-item-details.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='pôvodné detaily',
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF edited')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    item_id = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0].id
    state = _DummyState(data={'edit_invoice_id': invoice_id, 'edit_target_item_id': item_id, 'last_invoice_id': invoice_id})
    asyncio.run(
        invoice_edit_item_action(
            message=type(
                'M',
                (),
                {'text': 'vymazať detaily položky', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user},
            )(),
            state=state,
            config=config,
        )
    )
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw is None
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.answers[-1] == 'Detaily položky boli vymazané. Napíšte: schváliť, upraviť alebo zrušiť.'


def test_item_action_phrase_vymazat_detaily_reports_when_missing(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_target_item_id': 11, 'edit_invoice_id': 21})

    class _InvoiceServiceWithoutDetails:
        def __init__(self, db_path: Path) -> None:
            _ = db_path

        def get_invoice_for_supplier_by_id(self, *, supplier_telegram_id: int, invoice_id: int):  # noqa: ANN001
            _ = supplier_telegram_id
            return type('Invoice', (), {'id': invoice_id, 'supplier_telegram_id': supplier_telegram_id})()

        def get_items_by_invoice_id(self, invoice_id: int):  # noqa: ANN001
            _ = invoice_id
            return [type('Item', (), {'id': 11, 'item_description_raw': None})()]

    with patch('bot.handlers.invoice.InvoiceService', _InvoiceServiceWithoutDetails):
        asyncio.run(
            invoice_edit_item_action(
                message=type('M', (), {'from_user': message.from_user, 'text': 'vymazať detaily položky', 'answer': message.answer})(),
                state=state,
                config=config,
            )
        )
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.answers[-1] == 'Položka nemá žiadne detaily na vymazanie.'


def test_draft_numeric_edit_quantity_recalculates_total(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    draft = {
        'customer_name': 'Test',
        'issue_date': '2026-04-30',
        'delivery_date': '2026-04-30',
        'due_date': '2026-05-14',
        'invoice_number': '20260001',
        'items': [{'service_display_name': 'Servis', 'service_short_name': 'servis', 'quantity': 2.0, 'unit': 'ks', 'unit_price': 10.0, 'amount': 20.0}],
        'currency': 'EUR',
    }
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft, 'edit_target_item_index': 1, 'edit_item_action_mode': 'edit_item_quantity'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': message.from_user, 'text': '3', 'answer': message.answer})(), state=state, config=config))
    item = draft['items'][0]
    assert item['quantity'] == 3.0
    assert item['amount'] == 30.0
    assert draft['amount'] == 30.0
    assert message.answers[-1].startswith('Množstvo položky bolo upravené.')
    assert not message.documents


def test_draft_numeric_edit_unit_price_recalculates_total(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    draft = _draft_for_tests(contact_id=1)
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft, 'edit_target_item_index': 1, 'edit_item_action_mode': 'edit_item_unit_price'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': message.from_user, 'text': '250,50', 'answer': message.answer})(), state=state, config=config))
    item = draft['items'][0]
    assert item['unit_price'] == 250.5
    assert item['amount'] == 250.5
    assert draft['amount'] == 250.5
    assert message.answers[-1].startswith('Cena za m.j. bola upravená.')
    assert not message.documents


def test_draft_numeric_edit_total_recalculates_unit_price(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    draft = _draft_for_tests(contact_id=1)
    draft['items'][0]['quantity'] = 2.0
    draft['items'][0]['unit_price'] = 10.0
    draft['items'][0]['amount'] = 20.0
    draft['quantity'] = 2.0
    draft['unit_price'] = 10.0
    draft['amount'] = 20.0
    message = _DummyMessage(1)
    state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft, 'edit_target_item_index': 1, 'edit_item_action_mode': 'edit_item_total_amount'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': message.from_user, 'text': '50', 'answer': message.answer})(), state=state, config=config))
    item = draft['items'][0]
    assert item['amount'] == 50.0
    assert item['unit_price'] == 25.0
    assert draft['amount'] == 50.0
    assert message.answers[-1].startswith('Suma položky bola upravená.')
    assert not message.documents


def test_draft_numeric_invalid_and_negative_values_are_rejected(tmp_path: Path) -> None:
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'noop.db',
        storage_dir=tmp_path,
    )
    draft = _draft_for_tests(contact_id=1)

    invalid_message = _DummyMessage(1)
    invalid_state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft, 'edit_target_item_index': 1, 'edit_item_action_mode': 'edit_item_quantity'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': invalid_message.from_user, 'text': 'dve a pol', 'answer': invalid_message.answer})(), state=invalid_state, config=config))
    assert (
        'Hodnotu sa nepodarilo rozpoznať. Zadajte prosím množstvo, napr. 2 alebo 2,5.'
        in invalid_message.answers[-1]
    )
    assert '1500' not in invalid_message.answers[-1]
    assert _invoice_exact_value_recovery_hint() in invalid_message.answers[-1]

    for mode, value in [('edit_item_quantity', '-1'), ('edit_item_unit_price', '-0.5'), ('edit_item_total_amount', '-10')]:
        message = _DummyMessage(1)
        state = _DummyState(data={'edit_stage': 'draft', 'invoice_draft': draft, 'edit_target_item_index': 1, 'edit_item_action_mode': mode})
        asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': message.from_user, 'text': value, 'answer': message.answer})(), state=state, config=config))
        if mode == 'edit_item_quantity':
            assert 'Zadajte prosím množstvo, napr. 2 alebo 2,5.' in message.answers[-1]
            assert '1500' not in message.answers[-1]
        else:
            assert 'Zadajte prosím cenu, napr. 1500 alebo 1500,50.' in message.answers[-1]
            assert 'množstvo, napr. 2 alebo 2,5' not in message.answers[-1]
        assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_persisted_numeric_edit_total_rebuilds_pdf_and_updates_invoice_total(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 778
    db_path = tmp_path / 'edit-total.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(db_path=db_path, storage_dir=tmp_path, telegram_id=telegram_id, service_short_name='servis', service_display_name='Servis', item_description_raw=None)
    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda *, target_path, **kwargs: (target_path.parent.mkdir(parents=True, exist_ok=True), target_path.write_bytes(b'%PDF')))
    message = _DummyMessage(telegram_id)
    config = Config(bot_token='token', openai_api_key='key', openai_stt_model='whisper-1', openai_llm_model='gpt-4o', debug_invoice_transparency=False, db_path=db_path, storage_dir=tmp_path)
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    state = _DummyState(data={'edit_invoice_id': invoice_id, 'edit_target_item_id': item.id, 'edit_item_action_mode': 'edit_item_total_amount'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': message.from_user, 'text': '50', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))
    updated = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert updated.total_price == 50.0
    assert InvoiceService(db_path).get_invoice_by_id(invoice_id).total_amount == 50.0
    assert message.documents


def test_persisted_numeric_edit_quantity_and_unit_price_rebuild_pdf(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 779
    db_path = tmp_path / 'edit-quantity-unit-price.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis',
        item_description_raw=None,
    )
    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda *, target_path, **kwargs: (target_path.parent.mkdir(parents=True, exist_ok=True), target_path.write_bytes(b'%PDF')))
    config = Config(bot_token='token', openai_api_key='key', openai_stt_model='whisper-1', openai_llm_model='gpt-4o', debug_invoice_transparency=False, db_path=db_path, storage_dir=tmp_path)
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    original_unit_price = float(item.unit_price)

    quantity_message = _DummyMessage(telegram_id)
    quantity_state = _DummyState(data={'edit_invoice_id': invoice_id, 'edit_target_item_id': item.id, 'edit_item_action_mode': 'edit_item_quantity'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'text': '3', 'answer': quantity_message.answer, 'answer_document': quantity_message.answer_document, 'from_user': quantity_message.from_user})(), state=quantity_state, config=config))
    quantity_updated = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert quantity_updated.quantity == 3.0
    assert quantity_updated.total_price == round(3.0 * original_unit_price, 2)
    assert InvoiceService(db_path).get_invoice_by_id(invoice_id).total_amount == round(3.0 * original_unit_price, 2)
    assert quantity_message.documents

    unit_price_message = _DummyMessage(telegram_id)
    unit_price_state = _DummyState(data={'edit_invoice_id': invoice_id, 'edit_target_item_id': item.id, 'edit_item_action_mode': 'edit_item_unit_price'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'text': '50', 'answer': unit_price_message.answer, 'answer_document': unit_price_message.answer_document, 'from_user': unit_price_message.from_user})(), state=unit_price_state, config=config))
    unit_price_updated = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert unit_price_updated.unit_price == 50.0
    assert unit_price_updated.total_price == 150.0
    assert InvoiceService(db_path).get_invoice_by_id(invoice_id).total_amount == 150.0
    assert unit_price_message.documents


def test_persisted_numeric_invalid_and_negative_are_rejected_without_db_mutation(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 780
    db_path = tmp_path / 'edit-invalid.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(db_path=db_path, storage_dir=tmp_path, telegram_id=telegram_id, service_short_name='servis', service_display_name='Servis', item_description_raw=None)
    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(bot_token='token', openai_api_key='key', openai_stt_model='whisper-1', openai_llm_model='gpt-4o', debug_invoice_transparency=False, db_path=db_path, storage_dir=tmp_path)
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    before = (item.quantity, item.unit_price, item.total_price, InvoiceService(db_path).get_invoice_by_id(invoice_id).total_amount)

    for value in ['text', '-1']:
        message = _DummyMessage(telegram_id)
        state = _DummyState(data={'edit_invoice_id': invoice_id, 'edit_target_item_id': item.id, 'edit_item_action_mode': 'edit_item_total_amount'})
        asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': message.from_user, 'text': value, 'answer': message.answer, 'from_user': message.from_user})(), state=state, config=config))
        after_item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
        after_invoice_total = InvoiceService(db_path).get_invoice_by_id(invoice_id).total_amount
        assert (after_item.quantity, after_item.unit_price, after_item.total_price, after_invoice_total) == before
        assert 'Zadajte prosím cenu, napr. 1500 alebo 1500,50.' in message.answers[-1]
        assert 'množstvo, napr. 2 alebo 2,5' not in message.answers[-1]
        assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_persisted_total_edit_rejects_quantity_not_positive(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 781
    db_path = tmp_path / 'edit-total-qty-zero.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(db_path=db_path, storage_dir=tmp_path, telegram_id=telegram_id, service_short_name='servis', service_display_name='Servis', item_description_raw=None)
    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(bot_token='token', openai_api_key='key', openai_stt_model='whisper-1', openai_llm_model='gpt-4o', debug_invoice_transparency=False, db_path=db_path, storage_dir=tmp_path)
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    InvoiceService(db_path).update_item_financials(item_id=int(item.id), quantity=0.0, unit_price=float(item.unit_price), total_price=float(item.total_price))

    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id, 'edit_target_item_id': item.id, 'edit_item_action_mode': 'edit_item_total_amount'})
    asyncio.run(invoice_edit_item_numeric_value(message=type('M', (), {'from_user': message.from_user, 'text': '50', 'answer': message.answer, 'from_user': message.from_user})(), state=state, config=config))
    assert 'Množstvo položky musí byť väčšie ako 0.' in message.answers[-1]
    assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_single_item_default_targeting_is_applied_on_edit_entry(tmp_path: Path) -> None:
    telegram_id = 504
    db_path = tmp_path / 'single-item-target.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(tmp_path / 'x.pdf')})
    asyncio.run(process_invoice_postpdf_decision(message=message, state=state, config=config, decision_text='upraviť'))
    assert state.current_state == InvoiceStates.waiting_edit_scope
    asyncio.run(invoice_edit_scope(message=type('M', (), {'from_user': message.from_user, 'text': 'položka', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_item_action
    assert state.data.get('edit_target_item_index') == 1
    assert isinstance(state.data.get('edit_target_item_id'), int)


def test_multi_item_missing_target_triggers_bounded_clarification(tmp_path: Path) -> None:
    telegram_id = 505
    db_path = tmp_path / 'multi-item-target.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='prvá',
    )
    items = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)
    assert len(items) == 1
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO invoice_item '
                '(invoice_id, description_raw, description_normalized, item_description_raw, quantity, unit, unit_price, total_price) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (invoice_id, 'montaz', 'Montáž zariadenia', 'druhá', 1.0, 'ks', 100.0, 100.0),
        )
        connection.commit()

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(tmp_path / 'x.pdf')})
    asyncio.run(process_invoice_postpdf_decision(message=message, state=state, config=config, decision_text='upraviť'))
    assert state.current_state == InvoiceStates.waiting_edit_scope
    asyncio.run(invoice_edit_scope(message=type('M', (), {'from_user': message.from_user, 'text': 'položka', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_item_target

    asyncio.run(invoice_edit_item_target(message=type('M', (), {'from_user': message.from_user, 'text': 'uprav to', 'answer': message.answer})(), state=state, config=config))
    assert message.answers[-1].startswith('Prosím, spresnite číslo položky')


def test_multi_item_target_accepts_numeric_selection_via_bounded_resolver(tmp_path: Path) -> None:
    telegram_id = 506
    db_path = tmp_path / 'multi-item-target-numeric.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='prvá',
    )
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO invoice_item '
                '(invoice_id, description_raw, description_normalized, item_description_raw, quantity, unit, unit_price, total_price) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (invoice_id, 'montaz', 'Montáž zariadenia', 'druhá', 1.0, 'ks', 100.0, 100.0),
        )
        connection.commit()
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_item_target
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'from_user': message.from_user, 'text': '2', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_item_action
    assert state.data.get('edit_target_item_index') == 2


def test_multi_item_target_accepts_spoken_ordinal_via_bounded_resolver(tmp_path: Path) -> None:
    telegram_id = 507
    db_path = tmp_path / 'multi-item-target-spoken.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='prvá',
    )
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO invoice_item '
                '(invoice_id, description_raw, description_normalized, item_description_raw, quantity, unit, unit_price, total_price) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (invoice_id, 'montaz', 'Montáž zariadenia', 'druhá', 1.0, 'ks', 100.0, 100.0),
        )
        connection.commit()
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_item_target
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'from_user': message.from_user, 'text': 'druhá položka', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_item_action
    assert state.data.get('edit_target_item_index') == 2


def test_multi_item_target_ambiguous_keeps_state_and_requests_clarification(tmp_path: Path) -> None:
    telegram_id = 508
    db_path = tmp_path / 'multi-item-target-ambiguous.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='prvá',
    )
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO invoice_item '
                '(invoice_id, description_raw, description_normalized, item_description_raw, quantity, unit, unit_price, total_price) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (invoice_id, 'montaz', 'Montáž zariadenia', 'druhá', 1.0, 'ks', 100.0, 100.0),
        )
        connection.commit()
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_item_target
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'from_user': message.from_user, 'text': 'tú druhú servisnú', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_item_target
    assert message.answers[-1].startswith('Prosím, spresnite číslo položky')


def test_multi_item_target_out_of_range_keeps_state_and_fail_loud(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 509
    db_path = tmp_path / 'multi-item-target-out-of-range.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw='prvá',
    )
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO invoice_item '
                '(invoice_id, description_raw, description_normalized, item_description_raw, quantity, unit, unit_price, total_price) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (invoice_id, 'montaz', 'Montáž zariadenia', 'druhá', 1.0, 'ks', 100.0, 100.0),
        )
        connection.commit()

    async def _force_out_of_range(**kwargs):
        return '3'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _force_out_of_range)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_item_target
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'from_user': message.from_user, 'text': '3', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_item_target
    assert message.answers[-1].startswith('Taká položka neexistuje.')


def test_edit_invoice_number_free_value_updates_invoice_and_rebuilds_pdf(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 601
    db_path = tmp_path / 'edit-number-ok.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    old_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert old_invoice is not None
    old_number = old_invoice.invoice_number
    old_pdf = tmp_path / 'invoices' / f'{old_number}.pdf'
    old_pdf.parent.mkdir(parents=True, exist_ok=True)
    old_pdf.write_bytes(b'%PDF old')

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF edited-number')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(old_pdf)})

    asyncio.run(process_invoice_postpdf_decision(message=message, state=state, config=config, decision_text='upraviť'))
    asyncio.run(invoice_edit_scope(message=type('M', (), {'from_user': message.from_user, 'text': 'faktúra', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_invoice_action(message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť číslo faktúry', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(
        invoice_edit_invoice_number_value(
            message=type(
                'M',
                (),
                {'text': '20260099', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user},
            )(),
            state=state,
            config=config,
        )
    )

    updated_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert updated_invoice is not None
    assert updated_invoice.invoice_number == '20260099'
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.documents
    assert (tmp_path / 'invoices' / str(telegram_id) / '20260099.pdf').exists()
    assert not old_pdf.exists()
    assert message.answers[-1] == 'Číslo faktúry bolo upravené. Napíšte: schváliť, upraviť alebo zrušiť.'


def test_invoice_level_action_prompt_does_not_offer_contact_edit(tmp_path: Path) -> None:
    telegram_id = 610
    db_path = tmp_path / 'invoice-action-no-contact.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_scope
    asyncio.run(invoice_edit_scope(message=type('M', (), {'from_user': message.from_user, 'text': 'faktúra', 'answer': message.answer})(), state=state, config=config))
    assert 'upraviť kontakt' not in message.answers[-1]


def test_edit_scope_prompt_does_not_include_contact(tmp_path: Path) -> None:
    telegram_id = 612
    db_path = tmp_path / 'edit-scope-no-contact.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()
    asyncio.run(start_invoice_edit_flow(message=message, state=state, config=config, invoice_id=invoice_id))
    assert 'číslo/dátum/kontakt' not in message.answers[-1]
    assert 'číslo/dátum' in message.answers[-1]


def test_invoice_action_contact_text_is_unknown_and_state_is_preserved(tmp_path: Path) -> None:
    telegram_id = 611
    db_path = tmp_path / 'invoice-action-contact-unknown.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_action
    asyncio.run(
        invoice_edit_invoice_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť kontakt', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_invoice_action
    assert 'upraviť kontakt' not in message.answers[-1]


def test_unknown_edit_scope_input_repeats_menu_with_recovery_hint(tmp_path: Path) -> None:
    telegram_id = 614
    db_path = tmp_path / 'edit-scope-recovery.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(
        invoice_edit_scope(
            message=type('M', (), {'from_user': message.from_user, 'text': 'niečo iné', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )

    assert state.current_state == InvoiceStates.waiting_edit_scope
    assert 'Prosím, vyberte rozsah úpravy' in message.answers[-1]
    assert 'Ak chcete ukončiť túto akciu, napíšte „zrušiť“.' in message.answers[-1]
    assert 'Ak chcete začať odznova, použite /start.' in message.answers[-1]


def test_known_top_level_action_inside_edit_scope_gets_fsm_recovery_not_top_level_execution(tmp_path: Path) -> None:
    telegram_id = 615
    db_path = tmp_path / 'edit-scope-top-level-ignored.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(
        invoice_edit_scope(
            message=type('M', (), {'from_user': message.from_user, 'text': 'vytvor faktúru', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )

    assert state.current_state == InvoiceStates.waiting_edit_scope
    assert 'Prosím, vyberte rozsah úpravy' in message.answers[-1]
    assert 'Pošlite text faktúry' not in message.answers[-1]
    assert 'Ak chcete ukončiť túto akciu, napíšte „zrušiť“.' in message.answers[-1]


def test_edit_invoice_number_duplicate_rejected_and_state_kept(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 602
    db_path = tmp_path / 'edit-number-duplicate.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    other_invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='montaz',
        service_display_name='Montáž zariadenia',
        item_description_raw=None,
    )
    other_invoice = InvoiceService(db_path).get_invoice_by_id(other_invoice_id)
    assert other_invoice is not None
    old_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert old_invoice is not None
    old_number = old_invoice.invoice_number

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_number_value

    asyncio.run(
        invoice_edit_invoice_number_value(
            message=type('M', (), {'from_user': message.from_user, 'text': other_invoice.invoice_number, 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )

    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.invoice_number == old_number
    assert state.current_state == InvoiceStates.waiting_edit_invoice_number_value
    assert 'Číslo faktúry už existuje. Zadajte prosím iné číslo.' in message.answers[-1]
    assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_edit_invoice_number_invalid_value_rejected_and_kept_in_state(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 603
    db_path = tmp_path / 'edit-number-invalid.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    old_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert old_invoice is not None

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_number_value

    asyncio.run(
        invoice_edit_invoice_number_value(
            message=type('M', (), {'from_user': message.from_user, 'text': 'ABC-2026', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )

    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.invoice_number == old_invoice.invoice_number
    assert state.current_state == InvoiceStates.waiting_edit_invoice_number_value
    assert message.answers[-1].startswith('Neplatné číslo faktúry.')
    assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_edit_invoice_date_valid_value_updates_issue_date_and_rebuilds_pdf(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 604
    db_path = tmp_path / 'edit-date-ok.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    old_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert old_invoice is not None
    old_date = old_invoice.issue_date
    old_number = old_invoice.invoice_number
    old_pdf = tmp_path / 'invoices' / f'{old_number}.pdf'
    old_pdf.parent.mkdir(parents=True, exist_ok=True)
    old_pdf.write_bytes(b'%PDF old-date')

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF edited-date')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(old_pdf)})

    asyncio.run(process_invoice_postpdf_decision(message=message, state=state, config=config, decision_text='upraviť'))
    asyncio.run(invoice_edit_scope(message=type('M', (), {'from_user': message.from_user, 'text': 'faktúra', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_invoice_action(message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť dátum vystavenia', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type(
                'M',
                (),
                {'text': '15.03.2026', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user},
            )(),
            state=state,
            config=config,
        )
    )

    updated_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert updated_invoice is not None
    assert updated_invoice.issue_date == '2026-03-15'
    assert updated_invoice.issue_date != old_date
    assert updated_invoice.invoice_number == old_number
    assert message.documents
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.answers[-1] == 'Dátum vystavenia bol upravený. Napíšte: schváliť, upraviť alebo zrušiť.'


def test_edit_invoice_date_invalid_format_rejected_and_kept_in_state(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 605
    db_path = tmp_path / 'edit-date-invalid-format.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    old_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert old_invoice is not None

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'last_invoice_id': invoice_id,
            'edit_invoice_id': invoice_id,
            'edit_invoice_date_operation': 'edit_invoice_issue_date',
        }
    )
    state.current_state = InvoiceStates.waiting_edit_invoice_date_value

    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type('M', (), {'from_user': message.from_user, 'text': '2026-03-15', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.issue_date == old_invoice.issue_date
    assert state.current_state == InvoiceStates.waiting_edit_invoice_date_value
    assert (
        'Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR, napr. 15.03.2026.'
        in message.answers[-1]
    )
    assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_edit_invoice_date_impossible_date_rejected_and_kept_in_state(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 606
    db_path = tmp_path / 'edit-date-impossible.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    old_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert old_invoice is not None

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'last_invoice_id': invoice_id,
            'edit_invoice_id': invoice_id,
            'edit_invoice_date_operation': 'edit_invoice_issue_date',
        }
    )
    state.current_state = InvoiceStates.waiting_edit_invoice_date_value

    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type('M', (), {'from_user': message.from_user, 'text': '31.02.2026', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.issue_date == old_invoice.issue_date
    assert state.current_state == InvoiceStates.waiting_edit_invoice_date_value
    assert (
        'Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR, napr. 15.03.2026.'
        in message.answers[-1]
    )
    assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_edit_invoice_date_generic_action_requires_clarification(tmp_path: Path) -> None:
    telegram_id = 607
    db_path = tmp_path / 'edit-date-clarify.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_action
    asyncio.run(
        invoice_edit_invoice_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť dátum', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_invoice_action
    assert message.answers[-1] == 'Ktorý dátum chcete upraviť: vystavenia, dodania alebo splatnosti?'


def test_edit_invoice_delivery_date_success(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 608
    db_path = tmp_path / 'edit-delivery-ok.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id, 'last_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_action
    asyncio.run(
        invoice_edit_invoice_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť dátum dodania', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_invoice_date_value
    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type(
                'M',
                (),
                {
                    'text': '10.04.2026',
                    'answer': message.answer,
                    'answer_document': message.answer_document,
                    'from_user': message.from_user,
                },
            )(),
            state=state,
            config=config,
        )
    )
    updated_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert updated_invoice is not None
    assert updated_invoice.delivery_date == '2026-04-10'
    assert message.answers[-1] == 'Dátum dodania bol upravený. Napíšte: schváliť, upraviť alebo zrušiť.'


def test_edit_invoice_due_date_rejects_before_issue_date(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 609
    db_path = tmp_path / 'edit-due-invalid.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id, 'last_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_action
    asyncio.run(
        invoice_edit_invoice_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť dátum splatnosti', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type('M', (), {'from_user': message.from_user, 'text': '01.01.2026', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_invoice_date_value
    assert (
        message.answers[-1]
        and 'Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.'
        in message.answers[-1]
    )
    assert _invoice_exact_value_recovery_hint() in message.answers[-1]


def test_edit_invoice_date_voice_input_is_normalized_via_bounded_contract(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 613
    db_path = tmp_path / 'edit-date-voice-contract.db'
    init_db(db_path)
    invoice_id = _create_editable_invoice(
        db_path=db_path,
        storage_dir=tmp_path,
        telegram_id=telegram_id,
        service_short_name='servis',
        service_display_name='Servis zariadenia',
        item_description_raw=None,
    )
    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', lambda **kwargs: None)
    captured: dict[str, str] = {}

    async def _normalize_date(**kwargs):
        captured['date_field'] = str(kwargs.get('date_field'))
        captured['user_input_text'] = str(kwargs.get('user_input_text'))
        return '11.05.2026'

    monkeypatch.setattr('bot.handlers.invoice.resolve_invoice_date_normalization', _normalize_date)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState(data={'edit_invoice_id': invoice_id, 'last_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_action
    asyncio.run(
        invoice_edit_invoice_action(
            message=type('M', (), {'from_user': message.from_user, 'text': 'upraviť dátum dodania', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type(
                'M',
                (),
                {
                    'text': 'jedenásteho mája 2026',
                    'answer': message.answer,
                    'answer_document': message.answer_document,
                    'from_user': message.from_user,
                },
            )(),
            state=state,
            config=config,
        )
    )
    updated_invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert updated_invoice is not None
    assert updated_invoice.delivery_date == '2026-05-11'
    assert captured['date_field'] == 'edit_invoice_delivery_date'
    assert captured['user_input_text'] == 'jedenásteho mája 2026'


def test_postpdf_missing_invoice_id_fails_loud_and_clears_state(tmp_path: Path) -> None:
    db_path = tmp_path / 'missing-id.db'
    init_db(db_path)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    for decision_text in ('schváliť', 'zrušiť'):
        message = _DummyMessage(1)
        state = _DummyState(data={'last_pdf_path': str(tmp_path / 'missing.pdf')})
        asyncio.run(
            process_invoice_postpdf_decision(
                message=message,
                state=state,
                config=config,
                decision_text=decision_text,
            )
        )
        assert state.cleared is True
        assert message.answers[-1] == 'Návrh faktúry už nie je dostupný. Spustite /invoice znova.'
        assert 'Faktúra bola potvrdená.' not in message.answers


def test_postpdf_cancel_db_cleanup_happens_even_when_unlink_fails(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / 'unlink-fail.db'
    init_db(db_path)
    pdf_path = tmp_path / 'unlink-fail.pdf'
    invoice_id = _create_invoice_with_pdf(db_path, pdf_path)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(pdf_path)})

    def _fail_unlink(self, missing_ok=False):
        raise OSError('unlink failed')

    monkeypatch.setattr(Path, 'unlink', _fail_unlink)
    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=config,
            decision_text='zrušiť',
        )
    )

    assert InvoiceService(db_path).get_invoice_by_id(invoice_id) is None
    assert message.answers[-1] == 'Faktúra bola zrušená. Číslo faktúry nebolo finálne potvrdené.'


def test_waiting_pdf_decision_stt_ano_noise_approves_invoice(tmp_path: Path) -> None:
    db_path = tmp_path / 'noisy-unknown.db'
    init_db(db_path)
    pdf_path = tmp_path / 'noisy-unknown.pdf'
    invoice_id = _create_invoice_with_pdf(db_path, pdf_path)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(pdf_path)})

    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=config,
            decision_text='Ah, não.',
        )
    )

    assert state.cleared is True
    assert message.answers[-1] == 'Faktúra bola potvrdená.'
    invoice = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert invoice is not None
    assert invoice.status == 'pripravena'
    assert pdf_path.exists()


def test_waiting_pdf_decision_unknown_logs_contract_gap_and_does_not_cancel(tmp_path: Path, caplog) -> None:
    db_path = tmp_path / 'unknown-contract-gap.db'
    init_db(db_path)
    pdf_path = tmp_path / 'unknown-contract-gap.pdf'
    invoice_id = _create_invoice_with_pdf(db_path, pdf_path)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=True,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(1)
    state = _DummyState(data={'last_invoice_id': invoice_id, 'last_pdf_path': str(pdf_path)})
    state.current_state = InvoiceStates.waiting_pdf_decision.state

    async def _resolver(**kwargs):
        diagnostics = kwargs.get('diagnostics')
        if isinstance(diagnostics, dict):
            diagnostics.update(
                {
                    'raw_model_output': '{"canonical":"unknown"}',
                    'normalized_output': 'unknown',
                    'fallback_used': False,
                    'fallback_output': None,
                }
            )
        return 'unknown'

    with caplog.at_level(logging.INFO):
        from bot.handlers import invoice as invoice_module

        original = invoice_module.resolve_bounded_confirmation_reply
        invoice_module.resolve_bounded_confirmation_reply = _resolver
        try:
            asyncio.run(
                process_invoice_postpdf_decision(
                    message=message,
                    state=state,
                    config=config,
                    decision_text='random text',
                )
            )
        finally:
            invoice_module.resolve_bounded_confirmation_reply = original

    assert state.cleared is False
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'
    assert InvoiceService(db_path).get_invoice_by_id(invoice_id) is not None
    assert any('"event": "approval_unknown_contract_gap"' in rec.message for rec in caplog.records)


def test_waiting_pdf_decision_multilingual_destructive_synonyms_runtime_branching(tmp_path: Path) -> None:
    db_path = tmp_path / 'postpdf-multilingual.db'
    init_db(db_path)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    cancel_pdf = tmp_path / 'cancel-otmenit.pdf'
    cancel_invoice_id = _create_invoice_with_pdf(db_path, cancel_pdf)
    cancel_message = _DummyMessage(1)
    cancel_state = _DummyState(data={'last_invoice_id': cancel_invoice_id, 'last_pdf_path': str(cancel_pdf)})
    asyncio.run(
        process_invoice_postpdf_decision(
            message=cancel_message,
            state=cancel_state,
            config=config,
            decision_text='отменить',
        )
    )
    assert InvoiceService(db_path).get_invoice_by_id(cancel_invoice_id) is None
    assert cancel_message.answers[-1] == 'Faktúra bola zrušená. Číslo faktúry nebolo finálne potvrdené.'

    unknown_pdf = tmp_path / 'unknown-delete.pdf'
    unknown_invoice_id = _create_invoice_with_pdf(db_path, unknown_pdf)
    unknown_message = _DummyMessage(1)
    unknown_state = _DummyState(data={'last_invoice_id': unknown_invoice_id, 'last_pdf_path': str(unknown_pdf)})
    asyncio.run(
        process_invoice_postpdf_decision(
            message=unknown_message,
            state=unknown_state,
            config=config,
            decision_text='delete',
        )
    )
    assert InvoiceService(db_path).get_invoice_by_id(unknown_invoice_id) is not None
    assert unknown_message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'


def test_pdf_generation_failure_rolls_back_invoice_and_number(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9002
    db_path = tmp_path / 'rollback.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _failing_generate_invoice_pdf(**kwargs) -> None:
        raise RuntimeError('pdf failed')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _failing_generate_invoice_pdf)

    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'invoice_draft': {
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
        }
    )
    service = InvoiceService(db_path)

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='ano',
        )
    )

    assert state.cleared is True
    assert service.get_invoice_by_number('20260001') is None


def test_preview_failure_db_cleanup_happens_even_when_unlink_fails(tmp_path: Path, monkeypatch) -> None:
    telegram_id = 9003
    db_path = tmp_path / 'rollback-unlink.db'
    contact_id = _setup_profiles(db_path, telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )

    def _fake_generate_invoice_pdf(*, target_path, **kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF fake')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_generate_invoice_pdf)

    async def _fail_answer_document(*args, **kwargs) -> None:
        raise RuntimeError('send failed')

    def _fail_unlink(self, missing_ok=False):
        raise OSError('unlink failed')

    monkeypatch.setattr(_DummyMessage, 'answer_document', _fail_answer_document)
    monkeypatch.setattr(Path, 'unlink', _fail_unlink)

    message = _DummyMessage(telegram_id)
    state = _DummyState(
        data={
            'invoice_draft': {
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
        }
    )
    service = InvoiceService(db_path)

    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=config,
            confirmation_text='ano',
        )
    )

    assert state.cleared is True
    assert service.get_invoice_by_number('20260001') is None


def test_mark_existing_invoice_paid_confirmation_marks_followup_state(tmp_path: Path) -> None:
    telegram_id = 1
    db_path = tmp_path / 'mark-paid.db'
    init_db(db_path)
    invoice_id = _create_invoice_with_pdf(db_path, tmp_path / 'invoice.pdf', supplier_telegram_id=telegram_id)
    invoice_number = InvoiceService(db_path).get_invoice_for_supplier_by_id(
        supplier_telegram_id=telegram_id,
        invoice_id=invoice_id,
    ).invoice_number
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    state = _DummyState(
        {
            'pending_mark_paid_invoice_id': invoice_id,
            'pending_mark_paid_invoice_number': invoice_number,
        }
    )
    message = _DummyMessage(telegram_id, 'ano')

    asyncio.run(
        invoice_mark_existing_invoice_paid_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision='yes',
        )
    )

    with managed_connection(db_path) as connection:
        row = connection.execute(
            'SELECT payment_status, reminder_status, paid_at, drive_archive_status '
            'FROM invoice_followup_state WHERE invoice_id = ?',
            (invoice_id,),
        ).fetchone()
    assert row is not None
    assert row[0] == 'paid'
    assert row[1] == 'muted'
    assert row[2]
    assert row[3] == 'stub_requested_after_paid'
    assert state.cleared is True
    assert any('oznacil ako uhradenu' in answer.lower() for answer in message.answers)
    assert any('nie bankove potvrdenie' in answer.lower() for answer in message.answers)


def test_mark_existing_invoice_paid_confirmation_no_returns_to_menu(tmp_path: Path) -> None:
    telegram_id = 1
    db_path = tmp_path / 'mark-paid-no.db'
    init_db(db_path)
    invoice_id = _create_invoice_with_pdf(db_path, tmp_path / 'invoice.pdf', supplier_telegram_id=telegram_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    state = _DummyState({'pending_mark_paid_invoice_id': invoice_id, 'pending_mark_paid_invoice_number': '20260001'})
    message = _DummyMessage(telegram_id, 'nie')

    asyncio.run(
        invoice_mark_existing_invoice_paid_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision='no',
        )
    )

    with managed_connection(db_path) as connection:
        row = connection.execute('SELECT * FROM invoice_followup_state WHERE invoice_id = ?', (invoice_id,)).fetchone()
    assert row is None
    assert state.cleared is True
    assert any('/invoice' in answer for answer in message.answers)
