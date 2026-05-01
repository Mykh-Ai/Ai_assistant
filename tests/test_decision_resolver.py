from __future__ import annotations

import asyncio

import pytest

from bot.services.decision_resolver import (
    resolve_approve_edit_cancel,
    resolve_attachment_document_type_choice,
    resolve_attachment_route_choice,
    resolve_yes_no,
)


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('schvalit', 'approve'),
        ('schváliť', 'approve'),
        ('ano', 'approve'),
        ('áno', 'approve'),
        ('ok', 'approve'),
        ('upravit', 'edit'),
        ('upraviť', 'edit'),
        ('zrusit', 'cancel'),
        ('zrušiť', 'cancel'),
        ('nie', 'cancel'),
        ('no', 'cancel'),
        ('neviem', 'unknown'),
    ],
)
def test_preview_approve_edit_cancel_canonical_outputs(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name='invoice_preview_confirmation',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('schvalit', 'approve'),
        ('schváliť', 'approve'),
        ('ano', 'approve'),
        ('áno', 'approve'),
        ('ok', 'approve'),
        ('upravit', 'edit'),
        ('upraviť', 'edit'),
        ('zrusit', 'cancel'),
        ('zrušiť', 'cancel'),
        ('nie', 'cancel'),
        ('no', 'cancel'),
        ('neviem', 'unknown'),
    ],
)
def test_postpdf_approve_edit_cancel_canonical_outputs(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name='invoice_postpdf_decision',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('ano', 'yes'),
        ('áno', 'yes'),
        ('ok', 'yes'),
        ('nie', 'no'),
        ('no', 'no'),
        ('asi', 'unknown'),
    ],
)
def test_contact_semantic_intake_yes_no_canonical_outputs(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='contact_intake_confirm',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    'user_input',
    [
        'ano',
        '\u00e1no',
        'tak',
        'ok',
        '\u0442\u0430\u043a',
        '\u0434\u0430',
    ],
)
def test_idle_attachment_accounting_yes_variants_use_shared_resolver(user_input: str) -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='idle_attachment_accounting_proposal',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'yes'


def test_yes_no_stt_noise_is_unknown_for_idle_attachment_accounting() -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='idle_attachment_accounting_proposal',
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('vytvoriť kontakt', 'create_contact'),
        ('uložiť zmluvu', 'save_contract'),
        ('zrušiť', 'cancel'),
        ('asi neviem', 'unknown'),
    ],
)
def test_attachment_route_choice_canonical_outputs(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_attachment_route_choice(
            context_name='idle_attachment_route_choice',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('bloček', 'receipt'),
        ('prijatá faktúra', 'incoming_invoice'),
        ('zmluva', 'contract'),
        ('kontakt', 'contact_source'),
        ('zrušiť', 'cancel'),
        ('neviem', 'unknown'),
    ],
)
def test_attachment_document_type_choice_canonical_outputs(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_attachment_document_type_choice(
            context_name='idle_attachment_document_type_choice',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected
