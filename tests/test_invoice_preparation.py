import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
from types import SimpleNamespace

from pypdf import PdfReader
import pytest

from bot.handlers.decision_callbacks import decision_callback, invoice_preview_callback
from bot.handlers.invoice import (
    InvoiceStates, invoice_edit_item_numeric_value, invoice_edit_scope, invoice_rate_consent,
    process_invoice_postpdf_decision, process_invoice_slot_clarification, process_invoice_text,
)
from bot.invoice_preparation_migration import apply, audit
from bot.services.db import CONTACT_SCHEMA, LEGACY_INVOICE_SCHEMA, init_db, managed_connection
from bot.services.invoice_preparation import CalculationInputError, calculate_amounts, resolve_date, resolve_period
from bot.services.invoice_preparation_store import InvoicePreparationStore
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.llm_invoice_parser import validate_invoice_phase2_payload
from tests.test_decision_callbacks import (
    AUTHORIZED_ID, UNKNOWN_ID, _callback, _CallbackSourceMessage, _config, _DummyState, _setup_supplier_and_contact,
)


TEXT = 'Вистав Tech Company за два попередні тижні, 120 годин, відніми 14 ночей по 29 €'
ANCHOR = {
    'business_now_utc': '2026-11-16T13:00:00+00:00', 'business_today': '2026-11-16',
    'business_timezone': 'Europe/Bratislava', 'iso_year': 2026, 'iso_week': 47, 'iso_weekday': 1,
}
CALCULATION = {
    'period_intent': 'previous_two_completed_weeks', 'hours_total': '120',
    'lodging_mentioned': True, 'lodging_groups': [{'nights': 14, 'price_per_night': '29'}],
}


class Chat:
    def __init__(self, user_id=AUTHORIZED_ID):
        self.chat = SimpleNamespace(id=user_id, type='private')
        self.from_user = SimpleNamespace(id=user_id)
        self.text = TEXT
        self.message_id = 100
        self.replies = []
        self.documents = []
        self.removed_keyboards = []
        self.bot = self

    async def answer(self, text, *, reply_markup=None):
        self.message_id += 1
        self.replies.append((text, reply_markup, self.message_id))
        return SimpleNamespace(message_id=self.message_id)

    async def answer_document(self, document, *, caption=None):
        self.documents.append(Path(document.path))

    async def edit_message_reply_markup(self, *, chat_id, message_id, reply_markup):
        self.removed_keyboards.append((chat_id, message_id, reply_markup))


def payload(calculation, *, text=TEXT):
    return {
        'vstup': {'povodny_text': text, 'zisteny_jazyk': 'uk'},
        'zamer': {'nazov': 'create_invoice', 'istota': 1.0},
        'biznis_sk': {
            'odberatel_kandidat': 'Tech Company s.r.o.', 'polozka_povodna': None, 'termin_sluzby_sk': None,
            'mnozstvo': None, 'jednotka': None, 'suma': None, 'mena': 'EUR',
            'datum_dodania': None, 'splatnost_dni': None, 'datum_splatnosti': None,
            'calculation': calculation,
        },
        'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
    }


@pytest.fixture
def sandbox(tmp_path):
    config = replace(_config(tmp_path), allowed_telegram_user_ids=frozenset({AUTHORIZED_ID}))
    contact_id = _setup_supplier_and_contact(config.db_path)
    before = audit(config.db_path)
    apply(config.db_path, expected_fingerprint=before['fingerprint'], backup_path=tmp_path / 'before.db')
    with managed_connection(config.db_path) as connection:
        connection.execute('UPDATE contact SET default_hourly_rate_eur = ? WHERE id = ?', ('32', contact_id))
        connection.commit()
    return config, contact_id


def seed_prior_invoice(config, contact_id):
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=AUTHORIZED_ID, contact_id=contact_id, invoice_number='20260001',
        issue_date='2026-09-01', delivery_date='2026-09-01', due_date='2026-09-15',
        due_days=14, total_amount=999, currency='EUR', status='pripravena',
        items=[CreateInvoiceItemPayload('Pôvodný interný názov', 'Elektrické práce', None, 1, 'ks', 999, 999)],
    )


def mock_phase2(monkeypatch, calculation):
    async def intent(**kwargs):
        return 'create_invoice'

    async def parse(text, _key, _model, *, business_anchor, clarification_context=None):
        assert business_anchor == ANCHOR
        if clarification_context is not None:
            assert clarification_context['slot'] == 'calculation_hours'
            return validate_invoice_phase2_payload(payload({'hours_total': '100'}, text=text))
        return validate_invoice_phase2_payload(payload(calculation.copy(), text=text))

    monkeypatch.setattr('bot.handlers.invoice.business_clock', lambda: ANCHOR.copy())
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', intent)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', parse)


def callback_for(chat, *, user_id=AUTHORIZED_ID, token=None, message_id=None):
    _, keyboard, actual_id = chat.replies[-1]
    source = _CallbackSourceMessage()
    source.chat = chat.chat
    source.message_id = actual_id if message_id is None else message_id
    source.bot = chat.bot
    source.answer = chat.answer
    source.answer_document = chat.answer_document
    data = token or keyboard.inline_keyboard[0][0].callback_data
    assert len(data.encode()) <= 64
    return _callback(user_id, data, source)


def get_saved(config):
    with managed_connection(config.db_path) as connection:
        rows = connection.execute(
            'SELECT id, total_amount, calculation_bundle_json, pdf_path FROM invoice '
            'WHERE calculation_bundle_json IS NOT NULL ORDER BY id',
        ).fetchall()
    return [(invoice_id, total, json.loads(bundle), Path(pdf)) for invoice_id, total, bundle, pdf in rows]


def assert_pdf_amount(path, amount):
    text = '\n'.join(page.extract_text() for page in PdfReader(path).pages)
    assert f'Naúhradu{amount}EUR' in re.sub(r'\s+', '', text)


async def create_preview(config, chat, state):
    await process_invoice_text(message=chat, state=state, config=config, invoice_text=TEXT)


def test_public_create_uses_scoped_previous_service_and_one_final_pdf_item(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    assert state.current_state == InvoiceStates.waiting_confirm
    summary, preview = chat.replies[-2:]
    assert 'KW 45/2026' in summary[0] and 'KW 46/2026' in summary[0]
    assert '2026-11-13' in summary[0] and '3434.00 EUR' in summary[0]
    assert 'Rozpis hodín' in summary[0] and '20260001' in summary[0]
    assert preview[1] is not None and not get_saved(config)
    callback = callback_for(chat)
    asyncio.run(invoice_preview_callback(callback, state, config))
    assert state.current_state is None
    [(invoice_id, total, bundle, pdf)] = get_saved(config)
    assert total == 3434 and bundle['invoice_id'] == invoice_id
    assert bundle['net'] == '3434.00' and bundle['gross'] == '3840.00'
    assert bundle['hourly_rate'] == '32' and bundle['hours_by_kw'] is None
    assert bundle['lodging_groups'][0]['subtotal'] == '406.00'
    [item] = InvoiceService(config.db_path).get_items_by_invoice_id(invoice_id)
    assert item.quantity == 1 and item.total_price == 3434 and item.description_normalized == 'Elektrické práce'
    assert_pdf_amount(pdf, '3434.00')
    assert chat.removed_keyboards
    asyncio.run(invoice_preview_callback(callback, state, config))
    assert len(get_saved(config)) == 1


@pytest.mark.parametrize(('answer', 'future_rate'), [('áno', '40'), ('nie', '32')])
def test_explicit_rate_is_used_now_and_reused_only_with_separate_consent(sandbox, monkeypatch, answer, future_rate):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, {**CALCULATION, 'hourly_rate': '40'})
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    asyncio.run(invoice_preview_callback(callback_for(chat), state, config))
    store = InvoicePreparationStore(config.db_path, actor_id=AUTHORIZED_ID, workspace_id=None)
    assert state.current_state == InvoiceStates.waiting_rate_consent
    assert 'budúce faktúry' in chat.replies[-1][0]
    assert store.contact_rate(contact_id) == '32' and get_saved(config)[0][1] == 4394
    chat.text = answer
    asyncio.run(invoice_rate_consent(chat, state, config))
    assert store.contact_rate(contact_id) == future_rate
    assert state.current_state is None and get_saved(config)[0][1] == 4394


def test_first_invoice_asks_for_service_and_does_not_guess(sandbox, monkeypatch):
    config, _ = sandbox
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    assert state.current_state == InvoiceStates.waiting_slot_clarification
    assert 'presný názov služby' in chat.replies[-1][0] and not get_saved(config)
    asyncio.run(process_invoice_slot_clarification(
        message=chat, state=state, config=config, clarification_text='Elektroinštalačné práce',
    ))
    assert state.current_state == InvoiceStates.waiting_confirm
    assert state.data['invoice_draft']['service_display_name'] == 'Elektroinštalačné práce'


def test_new_preview_rejects_old_generic_wrong_actor_message_and_parallel_approve(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()

    async def journey():
        await create_preview(config, chat, state)
        old = callback_for(chat)
        edit = callback_for(chat, token=old.data.removesuffix('approve') + 'edit')
        await invoice_preview_callback(edit, state, config)
        assert state.current_state == InvoiceStates.waiting_edit_scope
        await invoice_edit_scope(chat, state, config, canonical_operation='edit_calculation_hours')
        await process_invoice_slot_clarification(message=chat, state=state, config=config, clarification_text='100 hodín')
        assert state.current_state == InvoiceStates.waiting_confirm
        assert state.data['invoice_draft']['amount'] == 2794
        current = callback_for(chat)
        await invoice_preview_callback(old, state, config)
        await invoice_preview_callback(callback_for(chat, user_id=UNKNOWN_ID), state, config)
        await invoice_preview_callback(callback_for(chat, message_id=old.message.message_id), state, config)
        await decision_callback(callback_for(chat, token='decision:approve'), state, config)
        assert state.current_state == InvoiceStates.waiting_confirm and not get_saved(config)
        assert old.answers[-1][1]
        await asyncio.gather(invoice_preview_callback(current, state, config),
                             invoice_preview_callback(current, state, config))

    asyncio.run(journey())
    assert len(get_saved(config)) == 1 and get_saved(config)[0][1] == 2794


def test_saved_edit_invalidates_historical_bundle_and_rolls_back_on_pdf_failure(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    asyncio.run(invoice_preview_callback(callback_for(chat), state, config))
    [(invoice_id, _, original_bundle, path)] = get_saved(config)
    original_pdf = path.read_bytes()
    [item] = InvoiceService(config.db_path).get_items_by_invoice_id(invoice_id)
    edit_state = _DummyState({
        'edit_stage': 'persisted', 'edit_invoice_id': invoice_id, 'edit_target_item_id': item.id,
        'edit_item_action_mode': 'edit_item_total_amount', 'invoice_workspace_id': '',
    }, InvoiceStates.waiting_edit_item_numeric_value.state)
    chat.text = '3500'

    def broken_pdf(**kwargs):
        kwargs['target_path'].write_bytes(b'partial')
        raise RuntimeError('synthetic PDF error')

    with monkeypatch.context() as patch:
        patch.setattr('bot.handlers.invoice.generate_invoice_pdf', broken_pdf)
        asyncio.run(invoice_edit_item_numeric_value(chat, edit_state, config))
    assert path.read_bytes() == original_pdf and get_saved(config)[0][1:3] == (3434, original_bundle)
    assert edit_state.current_state == InvoiceStates.waiting_edit_item_numeric_value.state

    asyncio.run(invoice_edit_item_numeric_value(chat, edit_state, config))
    [(edited_id, total, bundle, edited_pdf)] = get_saved(config)
    assert edited_id == invoice_id and edited_pdf == path and total == 3500
    assert bundle['status'] == 'invalidated' and bundle['historical_net'] == '3434.00'
    assert bundle['effective_invoice_total'] == '3500.00'
    assert_pdf_amount(path, '3500.00')
    asyncio.run(process_invoice_postpdf_decision(
        message=chat, state=edit_state, config=config, decision_text='zrušiť',
    ))
    assert edit_state.current_state is None and get_saved(config)[0][1] == 3500 and path.is_file()


@pytest.mark.parametrize(('today', 'expected'), [
    (date(2026, 11, 16), [(2026, 45), (2026, 46)]),
    (date(2027, 1, 4), [(2026, 52), (2026, 53)]),
])
def test_iso_weeks_use_the_runtime_anchor_across_year_boundary(today, expected):
    weeks, _, _ = resolve_period(CALCULATION, today=today, raw_text=TEXT)
    assert [(week['iso_year'], week['kw']) for week in weeks] == expected


def test_unstated_year_is_rejected_but_explicit_historical_date_is_preserved():
    intent = {'kind': 'date', 'day': 18, 'month': 11, 'year': 2023}
    today = date(2026, 11, 16)
    for raw in ('dodania 18.11.', 'dodania 18.11., suma 2023 EUR'):
        with pytest.raises(CalculationInputError):
            resolve_date(intent, today=today, raw_text=raw, slot='delivery', weeks=[])
    assert resolve_date(intent, today=today, raw_text='dodania 18.11.2023', slot='delivery', weeks=[]) == date(2023, 11, 18)
    with pytest.raises(CalculationInputError):
        resolve_period({'iso_weeks': [{'kw': 53, 'iso_year': 2027}]}, today=today, raw_text='KW53/2027')


def test_lodging_groups_and_explicit_gross_net_checks():
    calc = {
        'hours_total': '120', 'hourly_rate': '32', 'gross_amount': '3840', 'net_amount': '3495',
        'lodging_groups': [{'nights': 7, 'price_per_night': '15'}, {'nights': 8, 'price_per_night': '30'}],
    }
    result = calculate_amounts(calc, contact_rate='40', weeks=[])
    assert result['lodging_total'] == '345.00' and result['net'] == '3495.00'
    with pytest.raises(CalculationInputError):
        calculate_amounts({**calc, 'net_amount': '3150'}, contact_rate='40', weeks=[])
    no_lodging = calculate_amounts({'hours_total': '120'}, contact_rate='32', weeks=[])
    assert no_lodging['net'] == '3840.00' and no_lodging['lodging_groups'] == []


@pytest.mark.parametrize('legacy', [False, True])
def test_additive_migration_dry_run_backup_and_compatibility_startup(tmp_path, legacy):
    db = tmp_path / 'db.sqlite'
    if legacy:
        with managed_connection(db) as connection:
            connection.execute(CONTACT_SCHEMA.replace('    workspace_id TEXT,\n', '').replace(
                'UNIQUE(workspace_id, name)', 'UNIQUE(supplier_telegram_id, name)',
            ))
            connection.execute(LEGACY_INVOICE_SCHEMA)
            connection.commit()
    init_db(db)
    original_bytes = db.read_bytes()
    dry_run = audit(db)
    assert dry_run['pending'] == ['contact.default_hourly_rate_eur', 'invoice.calculation_bundle_json']
    assert db.read_bytes() == original_bytes
    with pytest.raises(ValueError, match='changed since dry-run'):
        apply(db, expected_fingerprint='stale', backup_path=tmp_path / 'not-created.sqlite')
    assert db.read_bytes() == original_bytes
    backup = tmp_path / 'backup.sqlite'
    expanded = apply(db, expected_fingerprint=dry_run['fingerprint'], backup_path=backup)
    assert not expanded['pending'] and audit(backup) == dry_run
    init_db(backup)
    init_db(db)
    assert not audit(db)['pending']
    with managed_connection(db) as connection:
        assert connection.execute('PRAGMA integrity_check').fetchall() == [('ok',)]


def test_owned_expired_preview_and_global_cancel_have_no_write(sandbox, monkeypatch):
    from bot.handlers.state_control import cancel_current_state

    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()

    async def journey():
        await create_preview(config, chat, state)
        expired = callback_for(chat)
        state.data['invoice_preview_binding']['expires_at'] = (datetime.now(UTC) - timedelta(minutes=16)).isoformat()
        await invoice_preview_callback(expired, state, config)
        assert state.current_state is None and 'vypršala' in chat.replies[-1][0]
        await create_preview(config, chat, state)
        await cancel_current_state(message=chat, state=state, config=config)
        assert state.current_state is None

    asyncio.run(journey())
    assert not get_saved(config) and len(chat.removed_keyboards) == 2


def test_creation_pdf_failure_removes_invoice_items_and_calculation(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))

    def partial_pdf(**kwargs):
        target = kwargs['target_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'partial')
        raise RuntimeError('synthetic PDF error')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', partial_pdf)
    asyncio.run(invoice_preview_callback(callback_for(chat), state, config))
    assert not get_saved(config) and state.current_state is None
    with managed_connection(config.db_path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM invoice').fetchone() == (1,)
        assert connection.execute('SELECT COUNT(*) FROM invoice_item').fetchone() == (1,)
    assert not list(config.storage_dir.glob('invoices/**/*.pdf'))


def test_dispatcher_command_voice_approval_and_access_gate(sandbox, monkeypatch):
    from aiogram import Bot
    from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, SendDocument
    from aiogram.types import CallbackQuery, Chat as TelegramChat, Message, Update, User
    from tests.test_archive_delivery_public_journeys import LocalSession, dispatcher, update

    config, contact_id = sandbox
    config = replace(config, bot_token='123456:synthetic-invoice-token')
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    (config.storage_dir / 'uploads').mkdir()
    transcriptions = []

    async def stt(path, _key, _model):
        transcriptions.append(path)
        return TEXT

    async def no_navigation(**kwargs):
        return 'pass_through'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', stt)
    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', no_navigation)

    class Session(LocalSession):
        def __init__(self):
            super().__init__()
            self.sent_pdfs = []
            self.edits = []

        async def make_request(self, bot, method, timeout=None):
            if isinstance(method, SendDocument):
                self.sent_pdfs.append(Path(method.document.path))
                return Message(
                    message_id=105, chat=TelegramChat(id=AUTHORIZED_ID, type='private'),
                    date=datetime.now(UTC),
                )
            if isinstance(method, EditMessageReplyMarkup):
                self.edits.append(method)
                return True
            if isinstance(method, AnswerCallbackQuery):
                return True
            return await super().make_request(bot, method, timeout)

    async def journey():
        session = Session()
        bot = Bot(config.bot_token, session=session)
        dp = dispatcher()
        state = dp.fsm.get_context(bot=bot, chat_id=AUTHORIZED_ID, user_id=AUTHORIZED_ID)
        await dp.feed_update(bot, update(1, voice=True, actor=UNKNOWN_ID), config=config)
        assert not transcriptions
        await dp.feed_update(bot, update(2, text='/invoice', actor=AUTHORIZED_ID), config=config)
        assert await state.get_state() == InvoiceStates.waiting_input.state
        await dp.feed_update(bot, update(3, voice=True, actor=AUTHORIZED_ID), config=config)
        assert len(transcriptions) == 1
        assert await state.get_state() == InvoiceStates.waiting_confirm.state
        assert '3434.00' in session.sent[-2].text
        token = session.sent[-1].reply_markup.inline_keyboard[0][0].callback_data
        binding = (await state.get_data())['invoice_preview_binding']
        callback = CallbackQuery(
            id='invoice-preview-test', from_user=User(id=AUTHORIZED_ID, is_bot=False, first_name='Synthetic'),
            chat_instance='synthetic-invoice-chat', data=token, message=Message(
                message_id=binding['message_id'], chat=TelegramChat(id=AUTHORIZED_ID, type='private'),
                date=datetime.now(UTC),
            ),
        )
        await dp.feed_update(bot, Update(update_id=4, callback_query=callback), config=config)
        assert await state.get_state() is None
        assert len(session.sent_pdfs) == len(session.edits) == 1
        assert session.edits[0].message_id == binding['message_id']
        assert_pdf_amount(session.sent_pdfs[0], '3434.00')
        await bot.session.close()
        await dp.storage.close()

    asyncio.run(journey())


def test_profile_rate_and_latest_service_do_not_cross_workspaces(tmp_path):
    from tests.test_workspace_invoice_service import _setup
    from bot.services.workspace_invoice_service import WorkspaceInvoiceService

    db_path = tmp_path / 'workspace.db'
    init_db(db_path)
    first, second, first_contact, second_contact = _setup(db_path)
    snapshot = audit(db_path)
    apply(db_path, expected_fingerprint=snapshot['fingerprint'], backup_path=tmp_path / 'old.db')
    with managed_connection(db_path) as connection:
        connection.execute('UPDATE contact SET default_hourly_rate_eur = ? WHERE id = ?', ('32', first_contact.id))
        connection.commit()
    WorkspaceInvoiceService(db_path).create_invoice_with_items(
        first, contact_id=first_contact.id, invoice_number='20260001', issue_date='2026-11-15',
        delivery_date='2026-11-15', due_date='2026-11-29', due_days=14, total_amount=100,
        currency='EUR', status='pripravena',
        items=[CreateInvoiceItemPayload('service', 'First supplier work', None, 1, None, 100, 100)],
    )
    first_store = InvoicePreparationStore(db_path, actor_id=first.actor_telegram_id, workspace_id=first.workspace_id)
    second_store = InvoicePreparationStore(db_path, actor_id=second.actor_telegram_id, workspace_id=second.workspace_id)
    assert first_store.contact_rate(first_contact.id) == '32'
    assert first_store.latest_contact_service(first_contact.id) == ('First supplier work', '20260001')
    assert second_store.contact_rate(first_contact.id) is None
    assert second_store.latest_contact_service(first_contact.id) is None
    assert second_store.contact_rate(second_contact.id) is None
    assert not second_store.change_contact_rate(first_contact.id, expected='32', replacement='40')


def test_compatibility_runtime_can_create_plain_invoice_after_new_data(sandbox, monkeypatch):
    from bot.services.service_alias_service import ServiceAliasService
    from bot.services.supplier_service import SupplierService

    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    asyncio.run(invoice_preview_callback(callback_for(chat), state, config))
    before = get_saved(config)
    init_db(config.db_path)

    async def legacy_payload(text, _key, _model, **kwargs):
        data = payload({}, text=text)
        data['biznis_sk'].update(polozka_povodna='elektro', termin_sluzby_sk='elektro', suma=150)
        return validate_invoice_phase2_payload(data)

    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', legacy_payload)
    supplier = SupplierService(config.db_path).get_by_telegram_id(AUTHORIZED_ID)
    ServiceAliasService(config.db_path).create_mapping(
        supplier_id=supplier.id, service_short_name='elektro', service_display_name='Elektrické práce',
    )
    compatibility = replace(config, invoice_preparation_enabled=False)
    asyncio.run(process_invoice_text(
        message=chat, state=state, config=compatibility, invoice_text='Faktúra Tech Company, elektro, 150 EUR',
    ))
    asyncio.run(invoice_preview_callback(callback_for(chat), state, compatibility))
    assert get_saved(config) == before
    record = InvoiceService(config.db_path).get_invoice_by_number('20260003')
    assert record.total_amount == 150
    assert_pdf_amount(Path(record.pdf_path), '150.00')
