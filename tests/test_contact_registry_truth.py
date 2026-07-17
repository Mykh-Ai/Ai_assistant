from __future__ import annotations

import pytest

from bot.config import Config, _parse_bounded_positive_int
from bot.services import product_truth
from bot.services.info_help import build_product_truth_guidance


def test_contact_registry_config_defaults_are_disabled_and_bounded() -> None:
    fields = Config.__dataclass_fields__
    assert fields['contact_registry_lookup_enabled'].default is False
    assert fields['contact_registry_pilot_workspace_ids'].default == frozenset()
    assert fields['contact_registry_timeout_seconds'].default == 5
    assert fields['contact_registry_max_results'].default == 5
    assert _parse_bounded_positive_int('1', env_name='RESULTS', maximum=10) == 1
    assert _parse_bounded_positive_int('10', env_name='RESULTS', maximum=10) == 10
    with pytest.raises(RuntimeError, match='positive integer'):
        _parse_bounded_positive_int('0', env_name='RESULTS', maximum=10)
    with pytest.raises(RuntimeError, match='at most 10'):
        _parse_bounded_positive_int('11', env_name='RESULTS', maximum=10)
    with pytest.raises(RuntimeError, match='at most 30'):
        _parse_bounded_positive_int('31', env_name='TIMEOUT', maximum=30)


def test_contacts_product_truth_matches_gated_registry_behavior() -> None:
    entry = next(
        item for item in product_truth.list_capabilities() if item.capability_id == 'contacts'
    )
    assert entry.status.value == 'partial'
    assert entry.canonical_actions == ('add_contact',)
    assert entry.commands == ('/contact', '/contact_add', '/add_kontakt')
    assert 'official Slovak company search by name or IČO' in entry.summary_for_user
    limitations = ' '.join(entry.current_limitations)
    assert 'disabled by default' in limitations
    assert 'IČ DPH is never inferred' in limitations
    assert 'commercial-registry scraping' in limitations
    assert 'background synchronization' in limitations


def test_info_help_explains_registry_contact_support_and_limits() -> None:
    answer = build_product_truth_guidance(
        user_input_text='Môžem vyhľadať firmu podľa IČO v registri?'
    )
    assert answer is not None
    assert 'Kontakty' in answer
    assert 'názvu alebo IČO' in answer
    assert 'predvolene vypnutý' in answer
    assert 'IČ DPH sa neodvodzuje' in answer
    assert '/add_kontakt' in answer
    assert 'explicitným potvrdením' in answer