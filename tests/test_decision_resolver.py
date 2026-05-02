from __future__ import annotations

import asyncio
import importlib
import inspect

import pytest

from bot.handlers import accounting_document_intake, invoice, officeflow_attachment_router, voice
from bot.services.decision_resolver import (
    resolve_approve_edit_cancel,
    resolve_attachment_document_type_choice,
    resolve_attachment_route_choice,
    resolve_yes_no,
)


officeflow_attachment_router_module = importlib.import_module('bot.handlers.officeflow_attachment_router')


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
    'context_name',
    ['invoice_preview_confirmation', 'invoice_postpdf_decision', 'accounting_document_intake_preview'],
)
@pytest.mark.parametrize(
    'user_input',
    [
        'schváliť',
        'schvalit',
        'potvrdiť',
        'potvrdit',
        'ano',
        'tak',
        'OK',
        'схвалити',
        'схвалить',
        'подтвердить',
        'підтвердити',
        'да',
        'так',
        'upraviť',
        'upravit',
        'opraviť',
        'opravit',
        'edit',
        'редагувати',
        'изменить',
        'исправить',
        'управить',
        'змінити',
        'zrušiť',
        'zrusit',
        'nie',
        'no',
        'cancel',
        'скасувати',
        'отменить',
        'зрушити',
        'зрушить',
        'видалити',
        'удалить',
        'Ah, não.',
    ],
)
def test_approve_edit_cancel_resolver_returns_only_canonical_outputs(context_name: str, user_input: str) -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) in {'approve', 'edit', 'cancel', 'unknown'}


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('схвалити', 'approve'),
        ('схвалить', 'approve'),
        ('подтвердить', 'approve'),
        ('підтвердити', 'approve'),
        ('редагувати', 'edit'),
        ('изменить', 'edit'),
        ('исправить', 'edit'),
        ('управить', 'edit'),
        ('змінити', 'edit'),
        ('скасувати', 'cancel'),
        ('отменить', 'cancel'),
        ('зрушити', 'cancel'),
        ('зрушить', 'cancel'),
        ('видалити', 'cancel'),
        ('удалить', 'cancel'),
    ],
)
def test_approve_edit_cancel_multilingual_variants_resolve_in_shared_layer(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name='accounting_document_intake_preview',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


def test_relevant_handlers_do_not_branch_on_legacy_approve_edit_cancel_tokens() -> None:
    sources = '\n'.join(
        [
            inspect.getsource(invoice.process_invoice_preview_confirmation),
            inspect.getsource(invoice.process_invoice_postpdf_decision),
            inspect.getsource(accounting_document_intake.handle_accounting_document_preview_decision_text),
            inspect.getsource(officeflow_attachment_router_module.handle_officeflow_accounting_proposal_text),
            inspect.getsource(voice.handle_voice),
        ]
    )

    for legacy_token in ("== 'schvalit'", "== 'upravit'", "== 'zrusit'"):
        assert legacy_token not in sources


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
