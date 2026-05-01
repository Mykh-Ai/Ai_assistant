from __future__ import annotations

import asyncio

import pytest

from bot.services.decision_resolver import resolve_approve_edit_cancel, resolve_yes_no


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
