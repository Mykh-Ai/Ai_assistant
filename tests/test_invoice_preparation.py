import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
import sys
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
from bot.services.invoice_preparation import CalculationInputError, business_clock, calculate_amounts, resolve_date, resolve_period
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


def seed_prior_invoice(config, contact_id, *, ambiguous=False):
    items = [CreateInvoiceItemPayload('Pôvodný interný názov', 'Elektrické práce', None, 1, 'ks', 999, 999)]
    if ambiguous:
        items.append(CreateInvoiceItemPayload('montáž', 'Montáž', None, 1, 'ks', 100, 100))
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=AUTHORIZED_ID, contact_id=contact_id, invoice_number='20260001',
        issue_date='2026-09-01', delivery_date='2026-09-01', due_date='2026-09-15',
        due_days=14, total_amount=sum(item.total_price for item in items), currency='EUR', status='pripravena',
        items=items,
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


@pytest.mark.parametrize('previous_rate', ['32', None])
@pytest.mark.parametrize('answer', ['áno', 'nie'])
def test_explicit_rate_is_used_now_and_reused_only_with_separate_consent(sandbox, monkeypatch, answer, previous_rate):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    with managed_connection(config.db_path) as connection:
        connection.execute('UPDATE contact SET default_hourly_rate_eur = ? WHERE id = ?', (previous_rate, contact_id))
        connection.commit()
    mock_phase2(monkeypatch, {**CALCULATION, 'hourly_rate': '40'})
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    asyncio.run(invoice_preview_callback(callback_for(chat), state, config))
    store = InvoicePreparationStore(config.db_path, actor_id=AUTHORIZED_ID, workspace_id=None)
    assert state.current_state == InvoiceStates.waiting_rate_consent
    assert 'budúce faktúry' in chat.replies[-1][0]
    assert ('namiesto 32 EUR/h' in chat.replies[-1][0]) == (previous_rate == '32')
    assert 'None' not in chat.replies[-1][0]
    saved = get_saved(config)
    assert store.contact_rate(contact_id) == previous_rate and saved[0][1] == 4394
    original_pdf = saved[0][3].read_bytes()
    chat.text = answer
    asyncio.run(invoice_rate_consent(chat, state, config))
    assert store.contact_rate(contact_id) == ('40' if answer == 'áno' else previous_rate)
    assert state.current_state is None and get_saved(config) == saved
    assert saved[0][3].read_bytes() == original_pdf


@pytest.mark.parametrize('item_count', [0, 1, 2])
@pytest.mark.parametrize('has_history', [False, True])
def test_missing_service_keeps_calculation(sandbox, monkeypatch, item_count, has_history):
    config, contact_id = sandbox
    if has_history:
        seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    if item_count:
        async def parse(text, *_args, **_kwargs):
            draft = payload(CALCULATION.copy(), text=text)
            draft['biznis_sk']['items'] = [{'termin_sluzby_sk': None, 'polozka_povodna': None} for _ in range(item_count)]
            return validate_invoice_phase2_payload(draft)

        monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', parse)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    if not has_history:
        assert state.current_state == InvoiceStates.waiting_slot_clarification
        assert 'presný názov služby' in chat.replies[-1][0] and not get_saved(config)
        asyncio.run(process_invoice_slot_clarification(
            message=chat, state=state, config=config, clarification_text='Elektroinštalačné práce',
        ))
    assert state.current_state == InvoiceStates.waiting_confirm
    draft = state.data['invoice_draft']
    assert draft['service_display_name'] == ('Elektrické práce' if has_history else 'Elektroinštalačné práce')
    assert draft['calculation']['hours_total'] == '120'
    assert draft['calculation']['lodging_total'] == '406.00'
    assert draft['amount'] == 3434


def test_date_range_correction_keeps_existing_endpoint_and_calculation(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    chat, state = Chat(), _DummyState()
    mock_phase2(monkeypatch, CALCULATION)
    text = 'Faktúra pre Tech Company od 29.12.2025 do 2.1., 120 hodín, 14 nocí po 29 EUR'

    async def parse(text, *_args, clarification_context=None, **_kwargs):
        if clarification_context:
            assert clarification_context['slot'] == 'calculation_period'
            calculation = {'period_end': {'kind': 'date', 'year': 2026, 'month': 1, 'day': 3}}
        else:
            calculation = {
                **CALCULATION, 'period_intent': 'explicit_dates',
                'period_start': {'kind': 'date', 'year': 2025, 'month': 12, 'day': 29},
                'period_end': {'kind': 'ambiguous'},
                'delivery_date': {'kind': 'date', 'month': 1, 'day': 2},
            }
        return validate_invoice_phase2_payload(payload(calculation, text=text))

    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', parse)
    asyncio.run(process_invoice_text(message=chat, state=state, config=config, invoice_text=text))
    assert state.current_state == InvoiceStates.waiting_slot_clarification
    assert not get_saved(config)
    asyncio.run(process_invoice_slot_clarification(
        message=chat, state=state, config=config, clarification_text='Do 3.1.2026',
    ))
    assert state.current_state == InvoiceStates.waiting_confirm
    draft = state.data['invoice_draft']
    assert draft['delivery_date'] == '2026-01-02'
    bundle = draft['calculation']
    assert (bundle['period_start'], bundle['period_end']) == ('2025-12-29', '2026-01-03')
    assert bundle['hours_total'] == '120' and bundle['net'] == '3434.00'


def test_latest_invoice_with_two_distinct_services_cannot_supply_one(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id, ambiguous=True)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    assert state.current_state == InvoiceStates.waiting_slot_clarification
    partial = state.data['invoice_partial_draft']
    assert partial['unresolved_slot'] == 'calculation_service'
    assert partial['parsed_draft']['calculation'] == CALCULATION
    assert not get_saved(config)


@pytest.mark.parametrize('modeled_date', [None, {'kind': 'date', 'year': 2026, 'month': 1, 'day': 2}])
def test_labeled_delivery_date_survives_model_omission_or_year_guess(sandbox, monkeypatch, modeled_date):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    monkeypatch.setattr('bot.handlers.invoice.business_clock', lambda: {**ANCHOR, 'business_today': '2026-12-30'})

    async def parse(text, *_args, **_kwargs):
        return validate_invoice_phase2_payload(payload({
            'hours_total': '20', 'hourly_rate': '40', 'delivery_date': modeled_date,
        }, text=text))

    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', parse)
    chat, state = Chat(), _DummyState()
    asyncio.run(process_invoice_text(
        message=chat, state=state, config=config,
        invoice_text='Vystav faktúru pre Tech Company za KW1, 20 h za 40 EUR/h. Dátum dodania je 2. januára.',
    ))
    assert state.current_state == InvoiceStates.waiting_confirm
    assert state.data['invoice_draft']['delivery_date'] == '2027-01-02'
    assert state.data['invoice_draft']['amount'] == 800


def test_bare_year_reply_is_bound_to_the_pending_delivery_date(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)

    async def parse(text, *_args, clarification_context=None, **_kwargs):
        assert clarification_context is None
        return validate_invoice_phase2_payload(payload({
            **CALCULATION, 'delivery_date': {'kind': 'date', 'month': 5, 'day': 18, 'year': 2023},
        }, text=text))

    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', parse)
    chat, state = Chat(), _DummyState()
    before = config.db_path.read_bytes()
    asyncio.run(process_invoice_text(
        message=chat, state=state, config=config,
        invoice_text='Faktúra pre Tech Company, 120 hodín, 14 nocí po 29 EUR, dodania 18.5., suma 2023',
    ))
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'calculation_delivery'
    asyncio.run(process_invoice_slot_clarification(message=chat, state=state, config=config, clarification_text='2022'))
    draft = state.data['invoice_draft']
    assert state.current_state == InvoiceStates.waiting_confirm
    assert draft['delivery_date'] == '2022-05-18' and draft['calculation']['hours_total'] == '120'
    assert config.db_path.read_bytes() == before and not chat.documents


def test_incomplete_week_group_reopens_same_draft_and_resolves_from_full_reply(sandbox, monkeypatch):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)

    async def parse(text, *_args, clarification_context=None, **_kwargs):
        period = {'period_intent': 'explicit_iso_weeks', 'iso_weeks': [{'kw': 45}]}
        calculation = period if clarification_context else {**CALCULATION, **period}
        return validate_invoice_phase2_payload(payload(calculation, text=text))

    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', parse)
    chat, state = Chat(), _DummyState()
    before = config.db_path.read_bytes()
    asyncio.run(process_invoice_text(message=chat, state=state, config=config,
                                     invoice_text='Faktúra Tech Company, KW45–?, 120 hodín'))
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'calculation_period'
    asyncio.run(process_invoice_slot_clarification(message=chat, state=state, config=config,
                                                   clarification_text='KW 45, 46'))
    bundle = state.data['invoice_draft']['calculation']
    assert state.current_state == InvoiceStates.waiting_confirm
    assert [week['kw'] for week in bundle['iso_weeks']] == [45, 46]
    assert bundle['hours_total'] == '120' and bundle['net'] == '3434.00'
    assert config.db_path.read_bytes() == before and not chat.documents


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


@pytest.mark.parametrize('phase', ['uncommitted', 'committed', 'missing_original', 'tampered_replacement'])
def test_crashed_saved_edit_recovers_pdf_to_sqlite_version(sandbox, monkeypatch, phase):
    config, contact_id = sandbox
    seed_prior_invoice(config, contact_id)
    mock_phase2(monkeypatch, CALCULATION)
    chat, state = Chat(), _DummyState()
    asyncio.run(create_preview(config, chat, state))
    asyncio.run(invoice_preview_callback(callback_for(chat), state, config))
    [(invoice_id, _, original_bundle, path)] = get_saved(config)
    [item] = InvoiceService(config.db_path).get_items_by_invoice_id(invoice_id)
    original = path.read_bytes()
    after_commit = phase == 'committed'
    if phase == 'missing_original':
        path.unlink()
    program = '''
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
from bot.handlers.invoice import _render_existing_invoice_pdf
from bot.services.contact_service import ContactService
from bot.services.invoice_preparation_store import InvoicePreparationStore
from bot.services.supplier_service import SupplierService

db, pdf, actor, invoice, item, phase = sys.argv[1:]
target = Path(pdf)
db = Path(db)
actor = int(actor)
replace = os.replace
connect = sqlite3.connect

class KillAfterCommit(sqlite3.Connection):
    def commit(self):
        super().commit()
        os._exit(91)

def kill_after_replace(source, destination):
    replace(source, destination)
    if Path(destination) == target:
        os._exit(91)

if phase == 'committed':
    sqlite3.connect = lambda *args, **kwargs: connect(*args, **kwargs, factory=KillAfterCommit)
else:
    os.replace = kill_after_replace

def render(revised, items, staged):
    _render_existing_invoice_pdf(
        invoice=SimpleNamespace(**revised), items=[SimpleNamespace(**dict(row)) for row in items],
        supplier=SupplierService(db).get_by_telegram_id(actor),
        contact=ContactService(db).get_by_id_for_supplier(telegram_id=actor, contact_id=revised['contact_id']),
        pdf_path=staged,
    )

InvoicePreparationStore(db, actor_id=actor, workspace_id=None).edit_with_calculation(
    int(invoice), pdf_path=target, item_id=int(item),
    item_changes={'unit_price': 3500.0, 'total_price': 3500.0},
    render_pdf=render,
)
'''
    result = subprocess.run([
        sys.executable, '-c', program, str(config.db_path), str(path), str(AUTHORIZED_ID),
        str(invoice_id), str(item.id), 'committed' if after_commit else 'uncommitted',
    ], capture_output=True, text=True, timeout=30)
    assert result.returncode == 91, result.stderr
    assert path.read_bytes() != original  # The child reached the actual replacement.
    assert get_saved(config)[0][1] == (3500 if after_commit else 3434)

    from bot.services.invoice_preparation_store import recover_pending_invoice_edits

    if phase == 'tampered_replacement':
        path.write_bytes(b'%PDF- unexpected contents')
        with pytest.raises(ValueError, match='changed outside'):
            recover_pending_invoice_edits(config.db_path, config.storage_dir)
        assert list(path.parent.glob('.invoice-edit-*/pending.json'))
        assert path.read_bytes() == b'%PDF- unexpected contents'
        assert get_saved(config)[0][1:3] == (3434, original_bundle)
        return
    recover_pending_invoice_edits(config.db_path, config.storage_dir)
    recover_pending_invoice_edits(config.db_path, config.storage_dir)
    [(saved_id, total, bundle, pdf)] = get_saved(config)
    assert saved_id == invoice_id and pdf == path
    assert not list(path.parent.glob('.invoice-edit-*'))
    if after_commit:
        assert total == 3500 and bundle['effective_invoice_total'] == '3500.00'
        assert_pdf_amount(path, '3500.00')
    else:
        assert total == 3434 and bundle == original_bundle
        if phase == 'missing_original':
            assert not path.exists()
        else:
            assert path.read_bytes() == original


@pytest.mark.parametrize(('today', 'expected'), [
    (date(2026, 11, 16), [(2026, 45), (2026, 46)]),
    (date(2027, 1, 4), [(2026, 52), (2026, 53)]),
])
def test_iso_weeks_use_the_runtime_anchor_across_year_boundary(today, expected):
    weeks, _, _ = resolve_period(CALCULATION, today=today, raw_text=TEXT)
    assert [(week['iso_year'], week['kw']) for week in weeks] == expected


def test_unsupported_year_is_ignored_but_explicit_historical_date_is_preserved():
    intent = {'kind': 'date', 'day': 18, 'month': 11, 'year': 2023}
    today = date(2026, 11, 16)
    for raw in ('dodania 18.11.', 'dodania 18.11., suma 2023 EUR'):
        assert resolve_date(intent, today=today, raw_text=raw, slot='delivery', weeks=[]) == date(2026, 11, 18)
    assert resolve_date(intent, today=today, raw_text='dodania 18.11.2023', slot='delivery', weeks=[]) == date(2023, 11, 18)
    with pytest.raises(CalculationInputError):
        resolve_period({'iso_weeks': [{'kw': 53, 'iso_year': 2027}]}, today=today, raw_text='KW53/2027')


@pytest.mark.parametrize(('today', 'month', 'day', 'expected'), [
    (date(2026, 12, 30), 1, 2, date(2027, 1, 2)),
    (date(2027, 1, 2), 12, 30, date(2026, 12, 30)),
    (date(2027, 1, 1), 9, 3, date(2026, 9, 3)),  # exactly 120 days behind
    (date(2027, 1, 1), 1, 31, date(2027, 1, 31)),  # exactly 30 days ahead
])
def test_yearless_date_uses_nearest_plausible_calendar_year(today, month, day, expected):
    assert resolve_date({'kind': 'date', 'month': month, 'day': day}, today=today,
                        raw_text=f'{day}.{month}.', slot='delivery', weeks=[]) == expected


@pytest.mark.parametrize(('month', 'day'), [(9, 2), (2, 1)])
def test_suspicious_yearless_date_asks_for_year(month, day):
    with pytest.raises(CalculationInputError, match='roka'):
        resolve_date({'kind': 'date', 'month': month, 'day': day}, today=date(2027, 1, 1),
                     raw_text=f'{day}.{month}.', slot='delivery', weeks=[])


@pytest.mark.parametrize(('day', 'kind', 'expected'), [
    (date(2027, 1, 1), 'yesterday', date(2026, 12, 31)),
    (date(2027, 1, 1), 'day_before_yesterday', date(2026, 12, 30)),
    (date(2027, 1, 1), 'last_weekday', date(2026, 12, 25)),
])
def test_relative_dates_use_business_day(day, kind, expected):
    assert resolve_date({'kind': kind, 'weekday': 5}, today=day, raw_text='', slot='delivery', weeks=[]) == expected


def test_business_clock_uses_bratislava_midnight(monkeypatch):
    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz):
            assert tz is UTC
            return cls(2026, 12, 31, 23, 2, tzinfo=UTC)

    monkeypatch.setattr('bot.services.invoice_preparation.datetime', FrozenClock)
    anchor = business_clock()
    assert anchor['business_today'] == '2027-01-01'
    assert (anchor['iso_year'], anchor['iso_week']) == (2026, 53)


@pytest.mark.parametrize(('today', 'text', 'expected'), [
    (date(2027, 1, 4), 'за два попередні тижні', [(2026, 52), (2026, 53)]),
    (date(2027, 1, 4), 'попередні два тижні, KW53', [(2026, 53)]),
    (date(2026, 12, 31), 'KW 1', [(2027, 1)]),
    (date(2027, 1, 1), 'KW 52 a KW 1', [(2026, 52), (2027, 1)]),
    (date(2027, 1, 1), 'KW 52 a 53, 40 EUR/h', [(2026, 52), (2026, 53)]),
    (date(2027, 1, 1), 'KW52/2022.', [(2022, 52)]),
])
def test_period_uses_stated_kw_or_calculates_relative_weeks(today, text, expected):
    result, _, _ = resolve_period({**CALCULATION, 'iso_weeks': [{'kw': 12, 'iso_year': None}]},
                                  today=today, raw_text=text)
    assert [(week['iso_year'], week['kw']) for week in result] == expected


def test_model_cannot_turn_relative_cardinal_week_into_numbered_week():
    with pytest.raises(CalculationInputError):
        resolve_period({'period_intent': 'explicit_iso_weeks', 'iso_weeks': [{'kw': 2}]},
                       today=date(2027, 1, 4), raw_text='за попередні 2 тижні')


@pytest.mark.parametrize(('raw_text', 'expected'), [
    ('KW 45, 46', [(2026, 45), (2026, 46)]),
    ('KW45–47', [(2026, 45), (2026, 46), (2026, 47)]),
    ('KW 45 та 46', [(2026, 45), (2026, 46)]),
    ('KW 45, 46 a 47', [(2026, 45), (2026, 46), (2026, 47)]),
    ('KW 45, 46, а також 47', [(2026, 45), (2026, 46), (2026, 47)]),
    ('KW 45 и 46, 40 EUR', [(2026, 45), (2026, 46)]),
    ('KW 45 až KW 47', [(2026, 45), (2026, 46), (2026, 47)]),
    ('KW 45 по 47', [(2026, 45), (2026, 46), (2026, 47)]),
    ('KW 52/2026–1/2027', [(2026, 52), (2026, 53), (2027, 1)]),
    ('KW 52–1', [(2026, 52), (2026, 53), (2027, 1)]),
    ('KW 45, 40,50 EUR', [(2026, 45)]),
])
def test_complete_explicit_week_group_outranks_partial_model_array(raw_text, expected):
    weeks, _, _ = resolve_period({**CALCULATION, 'iso_weeks': [{'kw': 45}]},
                                 today=date(2026, 11, 16), raw_text=raw_text)
    assert [(week['iso_year'], week['kw']) for week in weeks] == expected


@pytest.mark.parametrize('raw_text', [
    'KW45–?', 'KW 45 та 460', 'KW 45, 54', 'KW45 і KW?', 'KW45 та сорок шість',
    'KW46–45', 'KW45–46–47', 'KW45 або 46', 'KW45, 46/xx',
])
def test_incomplete_explicit_week_group_requires_clarification(raw_text):
    with pytest.raises(CalculationInputError) as error:
        resolve_period(CALCULATION, today=date(2026, 11, 16), raw_text=raw_text)
    assert error.value.slot == 'calculation_period'


@pytest.mark.parametrize('raw_text', [
    'Tech 2023 s.r.o., dodania 18.5.',
    'dodania 18.5., suma 2023',
    'dodania 18.5., faktúra číslo 2023-001',
    'dodania 18.5., faktúra číslo 2023-05-18',
    'Dátum dodania 18.5., dátum vystavenia 18.5.2023',
    'Дата поставки 18 травня, дата оплаты 18 мая 2023 года',
])
def test_year_in_another_field_cannot_authorize_suspicious_date(raw_text):
    intent = {'kind': 'date', 'day': 18, 'month': 5, 'year': 2023}
    with pytest.raises(CalculationInputError) as error:
        resolve_date(intent, today=date(2026, 11, 16), raw_text=raw_text, slot='delivery', weeks=[])
    assert error.value.slot == 'calculation_delivery'


def test_unrelated_year_does_not_prevent_nearby_yearless_date():
    intent = {'kind': 'date', 'day': 18, 'month': 11, 'year': 2023}
    assert resolve_date(intent, today=date(2026, 11, 16), raw_text='Tech 2023 s.r.o., dodania 18.11.',
                        slot='delivery', weeks=[]) == date(2026, 11, 18)


@pytest.mark.parametrize('raw_text', [
    'Dátum dodania 2023-05-18', 'dodania 18.5.2023', 'дата постачання 18 травня 2023 року',
    'дата поставки 18 мая 2023 года',
])
def test_year_attached_to_date_is_preserved_even_if_model_omits_it(raw_text):
    assert resolve_date({'kind': 'date', 'day': 18, 'month': 5}, today=date(2026, 11, 16),
                        raw_text=raw_text, slot='delivery', weeks=[]) == date(2023, 5, 18)


def test_historical_range_anchors_to_the_endpoint_with_actual_year_evidence():
    calculation = {
        'period_intent': 'explicit_dates',
        'period_start': {'kind': 'date', 'day': 27, 'month': 12, 'year': 2026},
        'period_end': {'kind': 'date', 'day': 3, 'month': 1, 'year': None},
    }
    _, start, end = resolve_period(calculation, today=date(2026, 11, 16),
                                   raw_text='od 27. decembra do 3. januára 2024')
    assert (start, end) == ('2023-12-27', '2024-01-03')


def test_due_date_label_owns_its_year_even_with_a_range_preposition():
    assert resolve_date({'kind': 'date', 'day': 18, 'month': 5}, today=date(2026, 11, 16),
                        raw_text='Splatnosť do 18. mája 2023', slot='due', weeks=[]) == date(2023, 5, 18)


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
    assert not first_store.change_contact_rate(second_contact.id, expected=None, replacement='40')
    assert second_store.change_contact_rate(second_contact.id, expected=None, replacement='40')
    assert not second_store.change_contact_rate(second_contact.id, expected=None, replacement='42')
    assert second_store.contact_rate(second_contact.id) == '40'
    assert first_store.contact_rate(first_contact.id) == '32'


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
