from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bot.config import Config
from bot.handlers import contacts
from bot.handlers.contacts import (
    ContactStates,
    _ensure_contact_session_active,
    _start_add_contact_from_source,
    contact_name_hint,
    contact_registry_action_callback,
    contact_registry_final_confirm,
    contact_registry_optional_contact_person,
    contact_registry_optional_email,
    contact_registry_optional_iban,
    contact_registry_pick_callback,
    contact_registry_required_dic,
    start_add_contact_intake,
)
from bot.services.access_control import AccessControlService
from bot.services.db import init_db
from bot.services.slovak_company_registry import (
    RegistryCompanyCandidate,
    RegistryCompanyDetails,
    RegistryLookupError,
    SlovakCompanyRegistry,
)
from bot.services.slovak_tax_registry import (
    TaxRegistryDetails,
    TaxRegistryLookupError,
)
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_profile_service import (
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


USER_ID = 9191


class _User:
    def __init__(self, user_id: int = USER_ID) -> None:
        self.id = user_id


class _Message:
    def __init__(self, user_id: int = USER_ID) -> None:
        self.from_user = _User(user_id)
        self.text: str | None = None
        self.document = None
        self.answers: list[str] = []
        self.answer_kwargs: list[dict] = []
        self.edited_markup = False

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)
        self.answer_kwargs.append(kwargs)

    async def edit_reply_markup(self, **_kwargs) -> None:
        self.edited_markup = True


class _State:
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
        return getattr(self.current_state, 'state', self.current_state)


class _Callback:
    def __init__(self, data: str, message: _Message, user_id: int = USER_ID) -> None:
        self.data = data
        self.message = message
        self.from_user = _User(user_id)
        self.callback_answers: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, *, show_alert: bool = False) -> None:
        self.callback_answers.append((text, show_alert))


class _FakeRegistry:
    def __init__(self, candidates=None, details=None, error: Exception | None = None) -> None:
        self.candidates = list(candidates or [])
        self.details = details or {}
        self.error = error
        self.search_calls: list[str] = []
        self.detail_calls: list[str] = []

    async def search(self, query: str):
        self.search_calls.append(query)
        if self.error is not None:
            raise self.error
        return list(self.candidates)

    async def get_details(self, subject_id: str):
        self.detail_calls.append(subject_id)
        if self.error is not None:
            raise self.error
        return self.details[subject_id]




class _PayloadRegistry(SlovakCompanyRegistry):
    def __init__(self, payloads: dict[str, object]) -> None:
        super().__init__()
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def _request_json(self, path: str, *, params=None):
        self.calls.append((path, params))
        return self.payloads[path]


class _FakeTaxRegistry:
    def __init__(self, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    async def lookup_by_ico(self, ico: str):
        self.calls.append(ico)
        if self.error is not None:
            raise self.error
        return self.result


def _provider_row(subject_id: int, name: str, ico: str, city: str) -> dict:
    return {
        'id': subject_id,
        'fullNames': [{'value': name, 'validFrom': '2020-01-01'}],
        'identifiers': [{'value': ico, 'validFrom': '2020-01-01'}],
        'addresses': [{'street': 'Hlavn?', 'buildingNumber': 1, 'postalCodes': ['83106'],
                       'municipality': {'value': city}, 'validFrom': '2020-01-01'}],
        'termination': None,
    }
def _config(tmp_path: Path, *, enabled: bool = False, pilots=frozenset()) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'contact.db',
        storage_dir=tmp_path,
        contact_registry_lookup_enabled=enabled,
        contact_registry_pilot_workspace_ids=frozenset(pilots),
    )


def _setup(config: Config) -> None:
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=1,
        role='owner',
    )
    WorkspaceProfileService(config.db_path).create_profile(
        actor_telegram_id=USER_ID,
        profile=SupplierProfile(
            telegram_id=USER_ID,
            name='Dodávateľ',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Hlavná 1, Bratislava',
            iban='SK3112000000198742637541',
            swift='TATRSKBX',
            email='owner@example.test',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        ),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
        workspace_id='ws_registry',
        storage_key='registry',
    )


def _candidate(subject_id: str, name: str, ico: str, city: str) -> RegistryCompanyCandidate:
    return RegistryCompanyCandidate(
        subject_id=subject_id,
        name=name,
        ico=ico,
        city=city,
        short_address=f'Hlavná 1, {city}',
        is_active=True,
        provider='slovak_rpo',
    )


def _details(subject_id: str, name: str, ico: str, *, dic=None, ic_dph=None) -> RegistryCompanyDetails:
    return RegistryCompanyDetails(
        subject_id=subject_id,
        name=name,
        ico=ico,
        dic=dic,
        ic_dph=ic_dph,
        address='Hlavná 12/3, 81101 Bratislava',
        city='Bratislava',
        is_active=True,
        provider_sources=('slovak_rpo',),
    )


def _contact_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute('SELECT COUNT(*) FROM contact').fetchone()[0])


def _active_workspace_selection(db_path: Path) -> str | None:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id = ?',
            (USER_ID,),
        ).fetchone()
    return None if row is None else str(row[0])


def test_registry_session_deadline_refreshes_with_typed_activity() -> None:
    now = datetime.now(UTC)
    initial_expiry = (now + timedelta(seconds=1)).isoformat()
    state = _State()
    state.current_state = ContactStates.registry_candidates
    state.data = {
        'contact_intake_expires_at': initial_expiry,
        'contact_registry_session': {
            'nonce': 'nonce',
            'expires_at': initial_expiry,
        },
    }
    message = _Message()

    assert asyncio.run(
        _ensure_contact_session_active(
            message=message,
            state=state,
            now=now,
        )
    )

    expected_expiry = now + timedelta(minutes=5)
    assert datetime.fromisoformat(state.data['contact_intake_expires_at']) == expected_expiry
    assert datetime.fromisoformat(state.data['contact_registry_session']['expires_at']) == expected_expiry



def test_all_contact_commands_share_one_registered_owner() -> None:
    handler = contacts.router.message.handlers[0]
    assert handler.callback is contacts.cmd_contact
    assert handler.filters[0].callback.commands == ('contact', 'contact_add', 'add_kontakt')


def test_registry_disabled_or_non_pilot_uses_manual_path_without_external_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for config in (
        _config(tmp_path / 'disabled', enabled=False),
        _config(tmp_path / 'nonpilot', enabled=True, pilots={'another_workspace'}),
    ):
        _setup(config)
        fake = _FakeRegistry(error=AssertionError('registry must not be called'))
        monkeypatch.setattr(contacts, '_registry_client', lambda _config: fake)
        state = _State()
        message = _Message()
        asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
        message.text = 'Manual Company s.r.o.'
        asyncio.run(contact_name_hint(message, state, config))
        assert state.current_state == ContactStates.source_after_name
        assert fake.search_calls == []
        assert _contact_count(config.db_path) == 0


def test_registry_error_and_zero_results_offer_manual_fallback_without_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for folder, fake in (
        ('error', _FakeRegistry(error=RegistryLookupError('registry_unavailable'))),
        ('empty', _FakeRegistry(candidates=[])),
    ):
        config = _config(tmp_path / folder, enabled=True)
        _setup(config)
        monkeypatch.setattr(contacts, '_registry_client', lambda _config, fake=fake: fake)
        state = _State()
        message = _Message()
        asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
        message.text = 'Missing Company'
        asyncio.run(contact_name_hint(message, state, config))
        assert state.current_state == ContactStates.registry_fallback
        assert 'ručne/PDF' in message.answers[-1]
        assert _contact_count(config.db_path) == 0


def test_multiple_candidates_are_bounded_buttons_and_stale_callbacks_write_nothing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _config(tmp_path, enabled=True)
    _setup(config)
    candidates = [
        _candidate('1', 'BAU ONE, s. r. o.', '11111111', 'Žilina'),
        _candidate('2', 'BAU TWO, s. r. o.', '22222222', 'Bratislava'),
    ]
    fake = _FakeRegistry(candidates=candidates, details={
        '1': _details('1', candidates[0].name, candidates[0].ico),
        '2': _details('2', candidates[1].name, candidates[1].ico),
    })
    monkeypatch.setattr(contacts, '_registry_client', lambda _config: fake)
    state = _State()
    message = _Message()
    asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
    message.text = 'bau'
    asyncio.run(contact_name_hint(message, state, config))

    assert state.current_state == ContactStates.registry_candidates
    keyboard = message.answer_kwargs[-1]['reply_markup']
    payloads = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert len(payloads) == 4
    assert all('BAU' not in payload and '11111111' not in payload for payload in payloads)
    assert _contact_count(config.db_path) == 0

    callback = _Callback('contact_registry_pick:wrong:0', message)
    asyncio.run(contact_registry_pick_callback(callback, state, config))
    assert callback.callback_answers[-1][1] is True
    assert state.current_state == ContactStates.registry_candidates
    assert _contact_count(config.db_path) == 0

    session = state.data['contact_registry_session']
    nonce = session['nonce']
    wrong_user = _Callback(f'contact_registry_pick:{nonce}:0', message, user_id=USER_ID + 1)
    asyncio.run(contact_registry_pick_callback(wrong_user, state, config))
    assert wrong_user.callback_answers[-1][1] is True
    assert _contact_count(config.db_path) == 0

    original_workspace = session['workspace_id']
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            'DELETE FROM active_workspace_selection WHERE telegram_id = ?',
            (USER_ID,),
        )
        connection.commit()
    assert _active_workspace_selection(config.db_path) is None
    session['workspace_id'] = 'wrong_workspace'
    state.data['contact_registry_session'] = session
    wrong_workspace = _Callback(f'contact_registry_pick:{nonce}:0', message)
    asyncio.run(contact_registry_pick_callback(wrong_workspace, state, config))
    assert wrong_workspace.callback_answers[-1][1] is True
    assert _active_workspace_selection(config.db_path) is None
    assert _contact_count(config.db_path) == 0
    session['workspace_id'] = original_workspace
    state.data['contact_registry_session'] = session

    invalid_index = _Callback(f'contact_registry_pick:{nonce}:9', message)
    asyncio.run(contact_registry_pick_callback(invalid_index, state, config))
    assert invalid_index.callback_answers[-1][1] is True
    assert _contact_count(config.db_path) == 0

    before_valid_callback = datetime.now(UTC)
    session['expires_at'] = (before_valid_callback + timedelta(seconds=1)).isoformat()
    state.data['contact_registry_session'] = session
    valid = _Callback(f'contact_registry_pick:{nonce}:1', message)
    asyncio.run(contact_registry_pick_callback(valid, state, config))
    refreshed_session = state.data['contact_registry_session']
    assert datetime.fromisoformat(refreshed_session['expires_at']) > before_valid_callback + timedelta(minutes=4)
    assert refreshed_session['expires_at'] == state.data['contact_intake_expires_at']
    assert state.current_state == ContactStates.registry_detail_preview
    assert fake.detail_calls == ['2']
    assert _contact_count(config.db_path) == 0

    repeated = _Callback(f'contact_registry_pick:{nonce}:1', message)
    asyncio.run(contact_registry_pick_callback(repeated, state, config))
    assert repeated.callback_answers[-1][1] is True
    assert fake.detail_calls == ['2']
    assert _contact_count(config.db_path) == 0

    state.current_state = ContactStates.registry_candidates
    session['expires_at'] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    state.data['contact_registry_session'] = session
    expired = _Callback(f'contact_registry_pick:{nonce}:0', message)
    asyncio.run(contact_registry_pick_callback(expired, state, config))
    assert expired.callback_answers[-1][1] is True
    assert _contact_count(config.db_path) == 0


def test_document_assisted_contact_iban_is_a_normalized_preview_draft(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    _setup(config)
    state = _State()
    message = _Message()

    asyncio.run(
        _start_add_contact_from_source(
            message=message,
            state=state,
            config=config,
            source_text='pridaj kontakt',
            document_text=(
                'Odberateľ: DOCUMENT COMPANY s.r.o.\n'
                'IČO: 87654321\nDIČ: 0987654321\n'
                'Adresa: Hlavná 12, Bratislava\n'
                'IBAN: sk31 1200 0000 1987 4263 7541'
            ),
        )
    )

    assert state.current_state == ContactStates.intake_confirm
    assert state.data['contact_intake_draft']['iban'] == 'SK3112000000198742637541'
    assert 'IBAN: SK3112000000198742637541' in message.answers[-1]
    assert _contact_count(config.db_path) == 0

def test_exact_registry_result_requires_typed_dic_optionals_and_final_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _config(tmp_path, enabled=True)
    _setup(config)
    candidate = _candidate('10', 'OFFICIAL COMPANY, s. r. o.', '87654321', 'Bratislava')
    fake = _FakeRegistry(
        candidates=[candidate],
        details={'10': _details('10', candidate.name, candidate.ico, dic=None, ic_dph=None)},
    )
    monkeypatch.setattr(contacts, '_registry_client', lambda _config: fake)
    state = _State()
    message = _Message()
    asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
    message.text = '87654321'
    asyncio.run(contact_name_hint(message, state, config))

    assert state.current_state == ContactStates.registry_detail_preview
    assert 'OFFICIAL COMPANY, s. r. o.' in message.answers[-1]
    assert 'IČ DPH: -' in message.answers[-1]
    assert _contact_count(config.db_path) == 0
    nonce = state.data['contact_registry_session']['nonce']

    supplement = _Callback(f'contact_registry_action:{nonce}:supplement', message)
    asyncio.run(contact_registry_action_callback(supplement, state, config))
    assert state.current_state == ContactStates.registry_required_dic

    message.text = '0987654321'
    asyncio.run(contact_registry_required_dic(message, state, config))
    message.text = 'contact@example.test'
    asyncio.run(contact_registry_optional_email(message, state, config))
    message.text = 'sk31 1200 0000 1987 4263 7541'
    asyncio.run(contact_registry_optional_iban(message, state, config))
    message.text = 'Eva Nováková'
    asyncio.run(contact_registry_optional_contact_person(message, state, config))
    assert state.current_state == ContactStates.registry_detail_preview
    assert state.data['contact_registry_draft']['iban'] == 'SK3112000000198742637541'
    assert 'Eva Nováková' in message.answers[-1]
    assert _contact_count(config.db_path) == 0

    save = _Callback(f'contact_registry_action:{nonce}:save', message)
    asyncio.run(contact_registry_action_callback(save, state, config))
    assert state.current_state == ContactStates.registry_final_confirm
    assert _contact_count(config.db_path) == 0

    message.text = 'áno'
    asyncio.run(
        contact_registry_final_confirm(
            message,
            state,
            config,
            canonical_decision='yes',
        )
    )
    assert state.current_state is None
    assert _contact_count(config.db_path) == 1
    with sqlite3.connect(config.db_path) as connection:
        row = connection.execute(
            'SELECT name, ico, dic, ic_dph, email, iban, contact_person, source_type '
            'FROM contact'
        ).fetchone()
    assert row == (
        'OFFICIAL COMPANY, s. r. o.',
        '87654321',
        '0987654321',
        None,
        'contact@example.test',
        'SK3112000000198742637541',
        'Eva Nováková',
        'registry',
    )

def test_exact_zevs_search_suppresses_noise_and_opens_detail_without_write(
    tmp_path: Path, monkeypatch,
) -> None:
    config = _config(tmp_path, enabled=True)
    _setup(config)
    exact = _provider_row(1, 'Zevs s. r. o.', '56055552', 'Bratislava - mestsk\u00e1 \u010das\u0165 Ra\u010da')
    registry = _PayloadRegistry({
        'search': {'results': [
            _provider_row(2, 'Ivona Klimaszevsk\u00e1', '11111111', 'Ko\u0161ice'),
            _provider_row(3, 'JUDr. Tom\u00e1\u0161 \u010c\u00ed\u017eevsk\u00fd, not\u00e1r', '22222222', 'Nitra'),
            _provider_row(4, 'Michal Kucharzewski OBCHODN\u00c1 KANCEL\u00c1RIA', '33333333', '\u017dilina'),
            _provider_row(5, 'Toni Bla\u017eevski', '44444444', 'Pre\u0161ov'),
            exact,
        ]},
        'entity/1': exact,
    })
    monkeypatch.setattr(contacts, '_registry_client', lambda _config: registry)
    state = _State()
    message = _Message()

    asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
    message.text = 'Zevs s.r.o.'
    asyncio.run(contact_name_hint(message, state, config))

    assert state.current_state == ContactStates.registry_detail_preview
    assert 'Zevs s. r. o.' in message.answers[-1]
    assert 'I\u010cO: 56055552' in message.answers[-1]
    assert 'Bratislava - mestsk\u00e1 \u010das\u0165 Ra\u010da' in message.answers[-1]
    assert 'Klimaszevsk\u00e1' not in '\n'.join(message.answers)
    assert registry.calls == [
        ('search', {'fullName': 'zevs', 'onlyActive': 'true'}),
        ('entity/1', None),
    ]
    assert _contact_count(config.db_path) == 0


def test_soft_single_result_requires_selection_but_two_exact_names_remain_listed(
    tmp_path: Path, monkeypatch,
) -> None:
    config = _config(tmp_path, enabled=True)
    _setup(config)
    registry = _PayloadRegistry({
        'search': {'results': [_provider_row(1, 'Zevs s.r.o.', '56055552', 'Bratislava')]},
        'entity/1': _provider_row(1, 'Zevs s.r.o.', '56055552', 'Bratislava'),
    })
    monkeypatch.setattr(contacts, '_registry_client', lambda _config: registry)
    state = _State()
    message = _Message()
    asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
    message.text = 'ZE VS'
    asyncio.run(contact_name_hint(message, state, config))

    assert state.current_state == ContactStates.registry_candidates
    assert registry.calls == [('search', {'fullName': 'ze vs', 'onlyActive': 'true'})]
    assert 'Zevs s.r.o.' in message.answers[-1]
    assert _contact_count(config.db_path) == 0

    second_config = _config(tmp_path / 'exact-two', enabled=True)
    _setup(second_config)
    exact_registry = _PayloadRegistry({'search': {'results': [
        _provider_row(1, 'Same Name s.r.o.', '11111111', 'Bratislava'),
        _provider_row(2, 'Same Name, s. r. o.', '22222222', 'Nitra'),
    ]}})
    monkeypatch.setattr(contacts, '_registry_client', lambda _config: exact_registry)
    exact_state = _State()
    exact_message = _Message()
    asyncio.run(start_add_contact_intake(
        message=exact_message, state=exact_state, config=second_config,
    ))
    exact_message.text = 'Same Name sro'
    asyncio.run(contact_name_hint(exact_message, exact_state, second_config))

    assert exact_state.current_state == ContactStates.registry_candidates
    assert 'I\u010cO: 11111111' in exact_message.answers[-1]
    assert 'I\u010cO: 22222222' in exact_message.answers[-1]
    assert 'Bratislava' in exact_message.answers[-1]
    assert 'Nitra' in exact_message.answers[-1]


def test_tax_enrichment_skips_typed_dic_and_does_not_repeat_on_save(
    tmp_path: Path, monkeypatch,
) -> None:
    config = replace(
        _config(tmp_path, enabled=True),
        contact_tax_lookup_enabled=True,
        financna_sprava_api_key='secret',
    )
    _setup(config)
    candidate = _candidate('10', 'Zevs s. r. o.', '56055552', 'Bratislava')
    registry = _FakeRegistry(
        candidates=[candidate],
        details={'10': _details('10', candidate.name, candidate.ico)},
    )
    tax = _FakeTaxRegistry(TaxRegistryDetails(
        ico='56055552', dic='2122222222', ic_dph=None,
        is_vat_registered=None, source_ids=('financna_sprava_income_tax',),
    ))
    monkeypatch.setattr(contacts, '_registry_client', lambda _config: registry)
    monkeypatch.setattr(contacts, '_tax_registry_client', lambda _config: tax)
    state = _State()
    message = _Message()
    asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
    message.text = '56055552'
    asyncio.run(contact_name_hint(message, state, config))

    assert state.current_state == ContactStates.registry_detail_preview
    assert 'DI\u010c: 2122222222' in message.answers[-1]
    assert 'I\u010c DPH: -' in message.answers[-1]
    assert 'slovak_rpo + financna_sprava' in message.answers[-1]
    assert tax.calls == ['56055552']
    assert _contact_count(config.db_path) == 0

    nonce = state.data['contact_registry_session']['nonce']
    supplement = _Callback(f'contact_registry_action:{nonce}:supplement', message)
    asyncio.run(contact_registry_action_callback(supplement, state, config))
    assert state.current_state == ContactStates.registry_optional_email

    state.current_state = ContactStates.registry_detail_preview
    save = _Callback(f'contact_registry_action:{nonce}:save', message)
    asyncio.run(contact_registry_action_callback(save, state, config))
    assert state.current_state == ContactStates.registry_final_confirm
    message.text = '\u00e1no'
    asyncio.run(contact_registry_final_confirm(
        message, state, config, canonical_decision='yes',
    ))
    assert _contact_count(config.db_path) == 1
    with sqlite3.connect(config.db_path) as connection:
        source_note = connection.execute(
            'SELECT source_note FROM contact WHERE ico=?', ('56055552',),
        ).fetchone()[0]
    assert source_note == 'slovak_rpo+financna_sprava'
    assert tax.calls == ['56055552']


def test_tax_failure_retains_rpo_and_enters_typed_dic(
    tmp_path: Path, monkeypatch,
) -> None:
    config = replace(
        _config(tmp_path, enabled=True),
        contact_tax_lookup_enabled=True,
        financna_sprava_api_key='secret',
    )
    _setup(config)
    candidate = _candidate('10', 'Zevs s. r. o.', '56055552', 'Bratislava')
    registry = _FakeRegistry(
        candidates=[candidate], details={'10': _details('10', candidate.name, candidate.ico)},
    )
    tax = _FakeTaxRegistry(error=TaxRegistryLookupError('tax_registry_unavailable'))
    monkeypatch.setattr(contacts, '_registry_client', lambda _config: registry)
    monkeypatch.setattr(contacts, '_tax_registry_client', lambda _config: tax)
    state = _State()
    message = _Message()
    asyncio.run(start_add_contact_intake(message=message, state=state, config=config))
    message.text = '56055552'
    asyncio.run(contact_name_hint(message, state, config))

    assert state.current_state == ContactStates.registry_detail_preview
    assert 'Zevs s. r. o.' in message.answers[-1]
    assert 'DI\u010c: -' in message.answers[-1]
    nonce = state.data['contact_registry_session']['nonce']
    supplement = _Callback(f'contact_registry_action:{nonce}:supplement', message)
    asyncio.run(contact_registry_action_callback(supplement, state, config))
    assert state.current_state == ContactStates.registry_required_dic
    assert tax.calls == ['56055552']
    assert _contact_count(config.db_path) == 0
