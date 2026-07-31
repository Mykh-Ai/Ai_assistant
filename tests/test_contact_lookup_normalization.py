from pathlib import Path

import pytest

from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db


TELEGRAM_ID = 12345


def _contact(name: str) -> ContactProfile:
    return ContactProfile(
        supplier_telegram_id=TELEGRAM_ID,
        name=name,
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Bratislava',
        email='test@example.com',
        contact_person=None,
        source_type='manual',
        source_note=None,
        contract_path=None,
    )


def _service(tmp_path: Path) -> ContactService:
    db_path = tmp_path / 'contacts.db'
    init_db(db_path)
    return ContactService(db_path)


def test_exact_match_unchanged(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('Tesla s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Tesla s.r.o.')

    assert result.state == 'exact_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'Tesla s.r.o.'


def test_case_insensitive_match(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('Tesla s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'TESLA S.R.O.')

    assert result.state == 'normalized_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'Tesla s.r.o.'


@pytest.mark.contract
@pytest.mark.integration
@pytest.mark.regression
@pytest.mark.parametrize(
    ('saved_name', 'query', 'expected_state', 'expected_saved_name'),
    [
        pytest.param(
            'Tesla s.r.o.',
            'Tesla sro',
            'normalized_match',
            'Tesla s.r.o.',
            id='legal-suffix-sro',
        ),
        pytest.param(
            'Tesla s.r.o.',
            'Tesla s. r. o.',
            'normalized_match',
            'Tesla s.r.o.',
            id='legal-suffix-spaced',
        ),
        pytest.param(
            'TECH COMPANY, s.r.o.',
            'Tech-Company',
            'normalized_match',
            'TECH COMPANY, s.r.o.',
            id='separator-hyphen',
        ),
        pytest.param(
            'TECH COMPANY, s.r.o.',
            'Tech Company',
            'normalized_match',
            'TECH COMPANY, s.r.o.',
            id='separator-spaces',
        ),
    ],
)
def test_normalized_contact_variant_match(
    tmp_path: Path,
    saved_name: str,
    query: str,
    expected_state: str,
    expected_saved_name: str,
) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact(saved_name))

    result = service.resolve_contact_lookup(TELEGRAM_ID, query)

    assert result.state == expected_state
    assert result.matched_contact is not None
    assert result.matched_contact.name == expected_saved_name


def test_multiple_candidates_state(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('TECH COMPANY s.r.o.'))
    service.create_or_replace(_contact('TECH-COMPANY, a.s.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Tech Company')

    assert result.state == 'multiple_candidates'
    assert result.matched_contact is None
    assert len(result.candidates) == 2


def test_no_match_state(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('Tesla s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Unknown Company')

    assert result.state == 'no_match'
    assert result.matched_contact is None
    assert result.candidates == []


def test_single_country_suffix_candidate_auto_resolves_when_unambiguous(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Real-Time Technologies')

    assert result.state == 'fuzzy_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'REALTIME TECHNOLOGIES SK, s.r.o.'
    assert [candidate.name for candidate in result.candidates] == ['REALTIME TECHNOLOGIES SK, s.r.o.']


def test_high_confidence_transcription_typo_auto_resolves(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Realtim Technologies SK')

    assert result.state == 'fuzzy_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'REALTIME TECHNOLOGIES SK, s.r.o.'


def test_high_confidence_pronunciation_variant_auto_resolves_with_unrelated_contact(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))
    service.create_or_replace(_contact('ZEVS s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Real Team Technologies')

    assert result.state == 'fuzzy_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'REALTIME TECHNOLOGIES SK, s.r.o.'
    assert [candidate.name for candidate in result.candidates] == ['REALTIME TECHNOLOGIES SK, s.r.o.']


def test_low_similarity_single_contact_does_not_auto_resolve(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Lajno')

    assert result.state == 'no_match'
    assert result.matched_contact is None
    assert result.candidates == []


def test_explicit_country_token_does_not_match_different_country(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'REALTIME TECHNOLOGIES CZ')

    assert result.state == 'no_match'
    assert result.matched_contact is None
    assert result.candidates == []


def test_missing_country_token_is_ambiguous_when_multiple_country_variants_exist(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES CZ, s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Real-Time Technologies')

    assert result.state == 'multiple_candidates'
    assert result.matched_contact is None
    assert [candidate.name for candidate in result.candidates] == [
        'REALTIME TECHNOLOGIES CZ, s.r.o.',
        'REALTIME TECHNOLOGIES SK, s.r.o.',
    ]


def test_confirmed_contact_alias_resolves_before_close_candidate(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))
    contact = service.get_by_name(TELEGRAM_ID, 'REALTIME TECHNOLOGIES SK, s.r.o.')
    assert contact is not None and contact.id is not None

    service.create_confirmed_contact_alias(
        supplier_telegram_id=TELEGRAM_ID,
        alias_text='Real-Time Technologies',
        contact_id=contact.id,
        source='test',
    )

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Real-Time Technologies')

    assert result.state == 'alias_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'REALTIME TECHNOLOGIES SK, s.r.o.'


def test_confirmed_contact_alias_rejects_cross_supplier_contact_id(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('REALTIME TECHNOLOGIES SK, s.r.o.'))
    foreign = ContactProfile(
        supplier_telegram_id=99999,
        name='Foreign Contact s.r.o.',
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Bratislava',
        email='foreign@example.com',
        contact_person=None,
        source_type='manual',
        source_note=None,
        contract_path=None,
    )
    service.create_or_replace(foreign)
    foreign_contact = service.get_by_name(99999, 'Foreign Contact s.r.o.')
    assert foreign_contact is not None and foreign_contact.id is not None

    with pytest.raises(ValueError):
        service.create_confirmed_contact_alias(
            supplier_telegram_id=TELEGRAM_ID,
            alias_text='Foreign Contact',
            contact_id=foreign_contact.id,
            source='test',
        )
