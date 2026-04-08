from pathlib import Path

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


def test_legal_suffix_sro_variant_match(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('Tesla s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Tesla sro')

    assert result.state == 'normalized_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'Tesla s.r.o.'


def test_legal_suffix_spaced_variant_match(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('Tesla s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Tesla s. r. o.')

    assert result.state == 'normalized_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'Tesla s.r.o.'


def test_separator_insensitive_match_hyphen(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('TECH COMPANY, s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Tech-Company')

    assert result.state == 'normalized_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'TECH COMPANY, s.r.o.'


def test_separator_insensitive_match_spaces(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_or_replace(_contact('TECH COMPANY, s.r.o.'))

    result = service.resolve_contact_lookup(TELEGRAM_ID, 'Tech Company')

    assert result.state == 'normalized_match'
    assert result.matched_contact is not None
    assert result.matched_contact.name == 'TECH COMPANY, s.r.o.'


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
