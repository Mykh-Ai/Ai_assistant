from bot.handlers.invoice import _contact_lookup_feedback
from bot.services.contact_service import ContactLookupResult, ContactProfile


def _profile(name: str, idx: int) -> ContactProfile:
    return ContactProfile(
        id=idx,
        supplier_telegram_id=1,
        name=name,
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Addr',
        email='a@example.com',
        contact_person=None,
        source_type='manual',
        source_note=None,
        contract_path=None,
    )


def test_feedback_for_no_match_is_non_assumptive() -> None:
    result = ContactLookupResult(
        state='no_match',
        matched_contact=None,
        candidates=[],
        raw_query='Unknown',
        normalized_query='unknown',
        compressed_query='unknown',
    )

    message = _contact_lookup_feedback(result)

    assert 'Skontrolujte názov' in message
    assert '/contact' in message


def test_feedback_for_multiple_candidates_mentions_similarity() -> None:
    result = ContactLookupResult(
        state='multiple_candidates',
        matched_contact=None,
        candidates=[_profile('TECH COMPANY s.r.o.', 1), _profile('TECH-COMPANY a.s.', 2)],
        raw_query='Tech Company',
        normalized_query='tech company',
        compressed_query='techcompany',
    )

    message = _contact_lookup_feedback(result)

    assert 'viac podobných kontaktov' in message
    assert 'TECH COMPANY s.r.o.' in message
