from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.contacts import (
    ContactStates,
    _process_source_after_name_step,
    _start_add_contact_from_source,
    contact_intake_from_document,
    contact_name_hint,
    process_contact_missing_fields,
    start_add_contact_intake,
)
from bot.services.contact_service import ContactService
from bot.services.db import init_db
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.llm_contact_parser import extract_contact_draft


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, user_id: int = 111) -> None:
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyDoc:
    def __init__(self, file_id: str, file_name: str) -> None:
        self.file_id = file_id
        self.file_name = file_name


class _DummyDocMessage(_DummyMessage):
    def __init__(self, caption: str | None, user_id: int = 111) -> None:
        super().__init__(user_id=user_id)
        self.caption = caption
        self.text = None
        self.document = _DummyDoc('doc-file-id', 'contract.pdf')


class _DummyBot:
    class _File:
        def __init__(self) -> None:
            self.file_path = 'remote/path'

    async def get_file(self, file_id: str):
        return self._File()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'%PDF')


class _DummyState:
    def __init__(self) -> None:
        self.data: dict = {}
        self.current_state = None

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()

    async def get_state(self):
        return self.current_state


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'contact.db',
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


def test_add_contact_from_text_pdf_like_content_with_missing_email(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    message = _DummyMessage()

    asyncio.run(
        _start_add_contact_from_source(
            message=message,
            state=state,
            config=config,
            source_text='pridaj kontakt',
            document_text='Objednávateľ: ZS s.r.o.\nIČO: 12345678\nDIČ: 1234567890\nAdresa: Hlavná 1, Košice',
            contract_path='storage/contracts/test.pdf',
        )
    )

    assert state.current_state == ContactStates.intake_missing
    assert 'e-mailovú adresu' in message.answers[-1]

    asyncio.run(
        process_contact_missing_fields(
            message=message,
            state=state,
            user_text='kontakt@zs.sk',
        )
    )
    assert state.current_state == ContactStates.intake_confirm
    assert 'Návrh kontaktu' in message.answers[-1]


def test_add_contact_missing_address_prompt(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    message = _DummyMessage()

    asyncio.run(
        _start_add_contact_from_source(
            message=message,
            state=state,
            config=config,
            source_text='додай контрагента',
            document_text='Objednávateľ: ZS s.r.o.\nIČO: 12345678\nDIČ: 1234567890\nEmail: kontakt@zs.sk',
        )
    )

    assert state.current_state == ContactStates.intake_missing
    assert 'určiť adresu' in message.answers[-1]


def test_contact_saved_after_confirmation(tmp_path: Path) -> None:
    from bot.handlers.contacts import process_contact_intake_confirm

    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    state.data['contact_intake_draft'] = {
        'name': 'ZS s.r.o.',
        'ico': '12345678',
        'dic': '1234567890',
        'ic_dph': '',
        'address': 'Hlavná 1, Košice',
        'email': 'kontakt@zs.sk',
        'contact_person': '',
        'contract_path': 'storage/contracts/test.pdf',
    }
    message = _DummyMessage()

    asyncio.run(
        process_contact_intake_confirm(
            message=message,
            state=state,
            config=config,
            answer_text='ano',
        )
    )

    saved = ContactService(config.db_path).get_by_name(111, 'ZS s.r.o.')
    assert saved is not None
    assert saved.contract_path == 'storage/contracts/test.pdf'


def test_idle_document_without_add_contact_intent_is_rejected(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    message = _DummyDocMessage(caption=None)

    async def _resolver(**kwargs):
        return 'unknown'

    monkeypatch.setattr('bot.handlers.contacts.resolve_semantic_action', _resolver)
    asyncio.run(contact_intake_from_document(message, state, config, _DummyBot()))

    assert message.answers
    assert 'Dokument som nepriradil ku kontaktu' in message.answers[-1]


def test_company_hint_is_preserved_for_extraction(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    message = _DummyDocMessage(caption='pridaj do kontaktov firmu ZS')
    captured: dict[str, str | None] = {}

    async def _resolver(**kwargs):
        return 'add_contact'

    async def _extractor(**kwargs):
        captured['company_hint'] = kwargs.get('company_hint')
        return {
            'company_name': 'ZS',
            'ico': '12345678',
            'dic': '1234567890',
            'ic_dph': None,
            'address': 'Hlavná 1, Košice',
            'email': 'kontakt@zs.sk',
            'contact_person': None,
            'role_ambiguity': '0',
        }

    monkeypatch.setattr('bot.handlers.contacts.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.contacts.extract_message_document_text', lambda *args, **kwargs: None)

    async def _doc_extract(*args, **kwargs):
        from bot.services.document_intake import DocumentIntakeResult

        return DocumentIntakeResult(
            status='text_pdf',
            extracted_text='Objednávateľ: ZS\nZhotoviteľ: Iná Firma',
            saved_path=tmp_path / 'contracts' / 'test.pdf',
        )

    monkeypatch.setattr('bot.handlers.contacts.extract_message_document_text', _doc_extract)
    monkeypatch.setattr('bot.handlers.contacts.extract_contact_draft', _extractor)

    asyncio.run(contact_intake_from_document(message, state, config, _DummyBot()))
    assert captured['company_hint'] == 'ZS'


def test_source_after_name_document_uses_saved_company_hint_without_caption(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    state.current_state = ContactStates.source_after_name
    state.data['contact_company_hint'] = 'ZS'
    message = _DummyDocMessage(caption=None)
    captured: dict[str, str | None] = {}

    async def _doc_extract(*args, **kwargs):
        from bot.services.document_intake import DocumentIntakeResult

        return DocumentIntakeResult(
            status='text_pdf',
            extracted_text='Objednávateľ: ZS\nZhotoviteľ: Iná Firma',
            saved_path=tmp_path / 'contracts' / 'test.pdf',
        )

    async def _extractor(**kwargs):
        captured['company_hint'] = kwargs.get('company_hint')
        return {
            'company_name': 'ZS',
            'ico': '12345678',
            'dic': '1234567890',
            'ic_dph': None,
            'address': 'Hlavná 1, Košice',
            'email': 'kontakt@zs.sk',
            'contact_person': None,
            'role_ambiguity': '0',
        }

    monkeypatch.setattr('bot.handlers.contacts.extract_message_document_text', _doc_extract)
    monkeypatch.setattr('bot.handlers.contacts.extract_contact_draft', _extractor)
    asyncio.run(_process_source_after_name_step(message, state, config, _DummyBot()))
    assert captured['company_hint'] == 'ZS'


def test_deterministic_ic_dph_extraction_uses_value_not_label() -> None:
    parsed = asyncio.run(
        extract_contact_draft(
            source_text='IČ DPH: SK1234567890',
            api_key=None,
            model='gpt-4o',
            company_hint=None,
        )
    )
    assert parsed['ic_dph'] == 'SK1234567890'


def test_role_ambiguity_keeps_partial_draft(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    message = _DummyMessage()

    async def _extractor(**kwargs):
        return {
            'company_name': None,
            'ico': '12345678',
            'dic': '1234567890',
            'ic_dph': None,
            'address': 'Hlavná 1, Košice',
            'email': None,
            'contact_person': None,
            'role_ambiguity': '1',
        }

    monkeypatch.setattr('bot.handlers.contacts.extract_contact_draft', _extractor)
    asyncio.run(
        _start_add_contact_from_source(
            message=message,
            state=state,
            config=config,
            source_text='ZS',
            document_text='Objednávateľ ... Zhotoviteľ ...',
            company_hint='ZS',
        )
    )

    assert state.current_state == ContactStates.intake_missing
    draft = state.data.get('contact_intake_draft')
    assert draft is not None
    assert draft['ico'] == '12345678'
    assert draft['dic'] == '1234567890'


def test_semantic_add_contact_enters_manual_wizard_step_one(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    message = _DummyMessage()

    asyncio.run(start_add_contact_intake(message=message, state=state, config=config))

    assert state.current_state == ContactStates.name_hint
    assert message.answers[-1] == 'V poriadku, vytvoríme nový kontakt. Najprv napíšte názov firmy.'


def test_name_hint_text_moves_to_source_after_name(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    message = _DummyMessage()
    message.text = 'ZS'
    message.document = None

    asyncio.run(contact_name_hint(message, state, config))

    assert state.current_state == ContactStates.source_after_name
    assert state.data['contact_company_hint'] == 'ZS'
    assert message.answers[-1] == 'Pošlite zmluvu/PDF alebo zadajte IČO.'


def test_source_after_name_manual_ico_valid_and_invalid(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup_supplier(config.db_path)
    state = _DummyState()
    state.current_state = ContactStates.source_after_name
    state.data['contact_company_hint'] = 'ZS'
    message = _DummyMessage()
    message.document = None
    message.text = 'bad'

    asyncio.run(_process_source_after_name_step(message, state, config))
    assert message.answers[-1] == 'Neplatné ICO. Formát: 8 číslic. Skúste znova:'

    message.text = '12345678'
    asyncio.run(_process_source_after_name_step(message, state, config))
    assert state.current_state == ContactStates.dic
    assert message.answers[-1] == '3/7 Zadajte DIC (10 číslic):'
