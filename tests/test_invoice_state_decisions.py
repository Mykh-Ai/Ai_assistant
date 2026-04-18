from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import (
    InvoiceStates,
    invoice_edit_invoice_action,
    invoice_edit_invoice_date_value,
    invoice_edit_description_value,
    invoice_edit_invoice_number_value,
    invoice_edit_item_action,
    invoice_edit_item_target,
    invoice_edit_scope,
    invoice_edit_service_value,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
)
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db, managed_connection
from bot.services.invoice_service import CreateInvoicePayload, InvoiceService
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, user_id: int) -> None:
        self.from_user = _DummyUser(user_id)
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

    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert isinstance(state.data.get('last_invoice_id'), int)
    assert state.data.get('last_invoice_number')
    assert state.data.get('last_pdf_path')
    assert message.documents


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
    assert 'Vytvorenie faktúry bolo zrušené.' in message.answers[-1]


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

    invoice_id = state.data.get('last_invoice_id')
    assert isinstance(invoice_id, int)
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


def test_waiting_confirm_noisy_transcript_returns_retry_unknown(tmp_path: Path) -> None:
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

    assert state.cleared is False
    assert message.answers[-1] == 'Prosím, odpovedzte áno alebo nie.'


def _create_invoice_with_pdf(db_path: Path, pdf_path: Path) -> int:
    service = InvoiceService(db_path)
    invoice_id = service.create_invoice_with_one_item(
        CreateInvoicePayload(
            supplier_telegram_id=777,
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
    edit_invoice_id = _create_invoice_with_pdf(db_path, edit_pdf_path)
    cancel_invoice_id = _create_invoice_with_pdf(db_path, cancel_pdf_path)
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
    asyncio.run(invoice_edit_scope(message=type('M', (), {'text': 'položka', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_item_action(message=type('M', (), {'text': 'zmeniť službu', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_service_value
    asyncio.run(invoice_edit_service_value(message=type('M', (), {'text': 'montaz', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))

    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.description_raw == 'montaz'
    assert item.description_normalized == 'Montáž zariadenia'
    assert item.item_description_raw == 'hala B'
    assert message.documents
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.answers[-1] == 'Služba položky bola upravená. Napíšte: schváliť, upraviť alebo zrušiť.'


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
    asyncio.run(invoice_edit_scope(message=type('M', (), {'text': 'položka', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_item_action(message=type('M', (), {'text': 'upraviť opis položky', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_description_value

    # set
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'text': 'práce v hale A', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw == 'práce v hale A'
    assert item.description_normalized == 'Servis zariadenia'
    assert state.current_state == InvoiceStates.waiting_pdf_decision
    assert message.answers[-1] == 'Opis položky bol upravený. Napíšte: schváliť, upraviť alebo zrušiť.'

    # replace
    state.data['last_invoice_id'] = invoice_id
    state.data['edit_invoice_id'] = invoice_id
    state.data['edit_target_item_id'] = item.id
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'text': 'práce v hale B', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw == 'práce v hale B'

    # clear
    state.data['last_invoice_id'] = invoice_id
    state.data['edit_invoice_id'] = invoice_id
    state.data['edit_target_item_id'] = item.id
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'text': 'vymaž opis', 'answer': message.answer, 'answer_document': message.answer_document, 'from_user': message.from_user})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw is None


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
    asyncio.run(invoice_edit_description_value(message=type('M', (), {'text': long_text, 'answer': message.answer})(), state=state, config=config))
    item = InvoiceService(db_path).get_items_by_invoice_id(invoice_id)[0]
    assert item.item_description_raw == 'pôvodný opis'
    assert 'príliš dlhý' in message.answers[-1]


def test_item_action_phrase_upravit_opis_routes_to_description_branch(tmp_path: Path) -> None:
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
            message=type('M', (), {'text': 'upraviť opis položky', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_description_value


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
            message=type('M', (), {'text': 'zmeniť službu', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_service_value


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
    asyncio.run(invoice_edit_scope(message=type('M', (), {'text': 'položka', 'answer': message.answer})(), state=state, config=config))
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
    asyncio.run(invoice_edit_scope(message=type('M', (), {'text': 'položka', 'answer': message.answer})(), state=state, config=config))
    assert state.current_state == InvoiceStates.waiting_edit_item_target

    asyncio.run(invoice_edit_item_target(message=type('M', (), {'text': 'uprav to', 'answer': message.answer})(), state=state, config=config))
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
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'text': '2', 'answer': message.answer})(), state=state, config=config))
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
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'text': 'druhá položka', 'answer': message.answer})(), state=state, config=config))
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
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'text': 'tú druhú servisnú', 'answer': message.answer})(), state=state, config=config))
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
    asyncio.run(invoice_edit_item_target(message=type('M', (), {'text': '3', 'answer': message.answer})(), state=state, config=config))
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
    asyncio.run(invoice_edit_scope(message=type('M', (), {'text': 'faktúra', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_invoice_action(message=type('M', (), {'text': 'upraviť číslo faktúry', 'answer': message.answer})(), state=state, config=config))
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
    assert (tmp_path / 'invoices' / '20260099.pdf').exists()
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
    asyncio.run(invoice_edit_scope(message=type('M', (), {'text': 'faktúra', 'answer': message.answer})(), state=state, config=config))
    assert 'upraviť kontakt' not in message.answers[-1]


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
            message=type('M', (), {'text': 'upraviť kontakt', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    assert state.current_state == InvoiceStates.waiting_edit_invoice_action
    assert 'upraviť kontakt' not in message.answers[-1]


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
            message=type('M', (), {'text': other_invoice.invoice_number, 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )

    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.invoice_number == old_number
    assert state.current_state == InvoiceStates.waiting_edit_invoice_number_value
    assert message.answers[-1] == 'Číslo faktúry už existuje. Zadajte prosím iné číslo.'


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
            message=type('M', (), {'text': 'ABC-2026', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )

    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.invoice_number == old_invoice.invoice_number
    assert state.current_state == InvoiceStates.waiting_edit_invoice_number_value
    assert message.answers[-1].startswith('Neplatné číslo faktúry.')


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
    asyncio.run(invoice_edit_scope(message=type('M', (), {'text': 'faktúra', 'answer': message.answer})(), state=state, config=config))
    asyncio.run(invoice_edit_invoice_action(message=type('M', (), {'text': 'upraviť dátum faktúry', 'answer': message.answer})(), state=state, config=config))
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
    assert message.answers[-1] == 'Dátum faktúry bol upravený. Napíšte: schváliť, upraviť alebo zrušiť.'


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
    state = _DummyState(data={'last_invoice_id': invoice_id, 'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_date_value

    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type('M', (), {'text': '2026-03-15', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.issue_date == old_invoice.issue_date
    assert state.current_state == InvoiceStates.waiting_edit_invoice_date_value
    assert message.answers[-1].startswith('Neplatný dátum.')


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
    state = _DummyState(data={'last_invoice_id': invoice_id, 'edit_invoice_id': invoice_id})
    state.current_state = InvoiceStates.waiting_edit_invoice_date_value

    asyncio.run(
        invoice_edit_invoice_date_value(
            message=type('M', (), {'text': '31.02.2026', 'answer': message.answer})(),
            state=state,
            config=config,
        )
    )
    reloaded = InvoiceService(db_path).get_invoice_by_id(invoice_id)
    assert reloaded is not None
    assert reloaded.issue_date == old_invoice.issue_date
    assert state.current_state == InvoiceStates.waiting_edit_invoice_date_value
    assert message.answers[-1].startswith('Neplatný dátum.')


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


def test_waiting_pdf_decision_noisy_transcript_stays_unknown_without_cleanup(tmp_path: Path) -> None:
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

    assert state.cleared is False
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'
    assert InvoiceService(db_path).get_invoice_by_id(invoice_id) is not None
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
                    decision_text='ЗРУШИТИ',
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
