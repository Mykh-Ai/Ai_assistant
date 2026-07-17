from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from bot.services.contact_service import ContactProfile
from bot.services.db import init_db
from bot.services.registry_contact_save import (
    RegistryContactConflict,
    RegistryContactDraft,
    RegistryContactSaveService,
)
from bot.services.slovak_company_registry import (
    RegistryLookupError,
    SlovakCompanyRegistry,
    normalize_company_search_name,
)
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_context import WorkspaceContext


ACTOR_ID = 771
WORKSPACE_ID = 'ws_registry_test'


def _context() -> WorkspaceContext:
    return WorkspaceContext(
        actor_telegram_id=ACTOR_ID,
        workspace_id=WORKSPACE_ID,
        workspace_display_name='Registry test',
        storage_key='registry-test',
        drive_folder_name='Registry test',
        membership_role='owner',
        supplier_id=1,
    )


def _candidate(subject_id: int, name: str, ico: str, *, city: str = 'Bratislava') -> dict:
    return {
        'id': subject_id,
        'fullNames': [{'value': name, 'validFrom': '2020-01-01'}],
        'identifiers': [{'value': ico, 'validFrom': '2020-01-01'}],
        'addresses': [{
            'street': 'Hlavná',
            'regNumber': 12,
            'buildingNumber': 3,
            'postalCodes': ['81101'],
            'municipality': {'value': city},
            'validFrom': '2020-01-01',
        }],
        'termination': None,
    }


class _StubRegistry(SlovakCompanyRegistry):
    def __init__(self, payloads: dict[str, object], *, max_results: int = 5) -> None:
        super().__init__(max_results=max_results)
        self.payloads = payloads
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def _request_json(self, path: str, *, params=None):
        self.calls.append((path, params))
        payload = self.payloads[path]
        if isinstance(payload, Exception):
            raise payload
        return payload


def _draft(**overrides) -> RegistryContactDraft:
    data = {
        'name': 'Example s.r.o.',
        'ico': '87654321',
        'dic': '0987654321',
        'ic_dph': None,
        'address': 'Hlavná 12/3, 81101 Bratislava',
        'email': None,
        'iban': None,
        'contact_person': None,
        'provider_sources': ('slovak_rpo',),
    }
    data.update(overrides)
    return RegistryContactDraft(**data)


def _existing(name: str, ico: str) -> ContactProfile:
    return ContactProfile(
        workspace_id=WORKSPACE_ID,
        supplier_telegram_id=ACTOR_ID,
        name=name,
        ico=ico,
        dic='0987654321',
        ic_dph='SK2020202020',
        address='Stará 1, Bratislava',
        email='preserve@example.test',
        iban='SK3112000000198742637541',
        contact_person='Eva',
        source_type='manual',
        source_note='original',
        contract_path='storage/contracts/original.pdf',
    )


def test_name_normalization_removes_diacritics_and_legal_suffix() -> None:
    assert normalize_company_search_name(' Žltá Firma, spol. s r. o. ') == 'zlta firma'


def test_exact_ico_search_is_bounded_and_deterministically_ranked() -> None:
    registry = _StubRegistry({
        'search': {'results': [
            _candidate(2, 'Other s.r.o.', '11111111'),
            _candidate(1, 'Exact s.r.o.', '87654321'),
        ]}
    }, max_results=1)

    result = asyncio.run(registry.search('87654321'))

    assert [item.ico for item in result] == ['87654321']
    assert registry.calls == [('search', {'identifier': '87654321', 'onlyActive': 'true'})]


def test_name_search_normalizes_query_and_ranks_exact_name_first() -> None:
    registry = _StubRegistry({'search': {'results': [
        _candidate(2, 'Beta Plus s.r.o.', '22222222'),
        _candidate(1, 'Béta, s.r.o.', '11111111'),
    ]}})

    result = asyncio.run(registry.search('Béta s.r.o.'))

    assert [item.subject_id for item in result] == ['1', '2']
    assert registry.calls[0][1] == {'fullName': 'beta', 'onlyActive': 'true'}


def test_inactive_provider_rows_are_ranked_after_active_rows_without_shape_error() -> None:
    inactive = _candidate(1, 'Beta s.r.o.', '11111111')
    inactive['termination'] = {'validFrom': '2024-01-01'}
    active = _candidate(2, 'Beta s.r.o.', '22222222')
    registry = _StubRegistry({'search': {'results': [inactive, active]}})

    result = asyncio.run(registry.search('Beta'))

    assert [item.subject_id for item in result] == ['2', '1']
    assert result[0].is_active is True
    assert result[1].is_active is False

def test_registry_malformed_search_shape_fails_closed() -> None:
    registry = _StubRegistry({'search': {'results': 'not-a-list'}})
    with pytest.raises(RegistryLookupError, match='registry_search_shape_invalid'):
        asyncio.run(registry.search('Example'))


def test_registry_details_never_infer_dic_or_ic_dph() -> None:
    registry = _StubRegistry({'entity/1': _candidate(1, 'Example s.r.o.', '87654321')})

    details = asyncio.run(registry.get_details('1'))

    assert details.dic is None
    assert details.ic_dph is None
    assert details.address == 'Hlavná 12/3, 81101 Bratislava'
    assert details.provider_sources == ('slovak_rpo',)


def test_registry_insert_and_update_preserve_identity_and_unsupplied_optional_fields(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    context = _context()
    contacts = WorkspaceContactService(db_path)
    original = contacts.create_or_replace(context, _existing('Example s.r.o.', '87654321'))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO invoice '
            '(workspace_id, supplier_telegram_id, contact_id, invoice_number, issue_date, '
            'delivery_date, due_date, due_days, total_amount, currency, status) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (WORKSPACE_ID, ACTOR_ID, original.id, '2026-001', '2026-07-17',
             '2026-07-17', '2026-07-31', 14, 10.0, 'EUR', 'draft'),
        )
        connection.commit()

    result = RegistryContactSaveService(db_path).save(
        context,
        _draft(address='Nová 2, Bratislava'),
    )

    assert result.mode == 'update'
    assert result.contact.id == original.id
    assert result.contact.email == 'preserve@example.test'
    assert result.contact.iban == 'SK3112000000198742637541'
    assert result.contact.contact_person == 'Eva'
    assert result.contact.contract_path == 'storage/contracts/original.pdf'
    assert result.contact.address == 'Nová 2, Bratislava'
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            'SELECT contact_id FROM invoice WHERE invoice_number=?', ('2026-001',)
        ).fetchone()[0] == original.id


def test_registry_explicit_optional_replacement_and_clear(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    context = _context()
    WorkspaceContactService(db_path).create_or_replace(
        context, _existing('Example s.r.o.', '87654321')
    )

    result = RegistryContactSaveService(db_path).save(
        context,
        _draft(
            email='',
            iban='SK8975000000000012345671',
            contact_person='Peter',
            email_supplied=True,
            iban_supplied=True,
            contact_person_supplied=True,
        ),
    )

    assert result.contact.email == ''
    assert result.contact.iban == 'SK8975000000000012345671'
    assert result.contact.contact_person == 'Peter'


def test_same_name_different_ico_is_refused_without_write(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    context = _context()
    contacts = WorkspaceContactService(db_path)
    existing = contacts.create_or_replace(context, _existing('Example s.r.o.', '11111111'))

    service = RegistryContactSaveService(db_path)
    assert service.inspect(context, _draft()).mode == 'name_conflict'
    with pytest.raises(RegistryContactConflict, match='name_conflict'):
        service.save(context, _draft())

    saved = contacts.get_by_id(context, existing.id)
    assert saved is not None
    assert saved.ico == '11111111'
    assert saved.source_type == 'manual'


def test_split_and_duplicate_ico_conflicts_are_refused(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    context = _context()
    contacts = WorkspaceContactService(db_path)
    contacts.create_or_replace(context, _existing('Example s.r.o.', '11111111'))
    contacts.create_or_replace(context, _existing('Other s.r.o.', '87654321'))
    service = RegistryContactSaveService(db_path)
    assert service.inspect(context, _draft()).mode == 'split_conflict'
    with pytest.raises(RegistryContactConflict, match='split_conflict'):
        service.save(context, _draft())

    contacts.create_or_replace(context, _existing('Third s.r.o.', '87654321'))
    duplicate_draft = _draft(name='New legal name s.r.o.')
    assert service.inspect(context, duplicate_draft).mode == 'ico_conflict'
    with pytest.raises(RegistryContactConflict, match='ico_conflict'):
        service.save(context, duplicate_draft)