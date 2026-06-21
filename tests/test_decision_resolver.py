from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
from pathlib import Path

import pytest

from bot.handlers import accounting_document_intake, invoice, officeflow_attachment_router, voice
from bot.services.decision_resolver import (
    is_global_cancel_text,
    resolve_accounting_document_category_preview_decision,
    resolve_accounting_document_category_selection,
    resolve_accounting_document_category_similar_decision,
    resolve_accounting_document_category_unknown_decision,
    resolve_approve_edit_cancel,
    resolve_attachment_document_type_choice,
    resolve_attachment_route_choice,
    resolve_global_cancel,
    resolve_yes_no,
)


officeflow_attachment_router_module = importlib.import_module('bot.handlers.officeflow_attachment_router')


# Project rule:
# Every new confirmation-like flow must register its context_name in one of
# these matrices. Handlers must call bot/services/decision_resolver.py and
# branch only on canonical outputs, not on raw localized reply text.
YES_NO_CONTEXTS = (
    'contact_confirm',
    'contact_intake_confirm',
    'onboarding_confirm',
    'delete_existing_invoice_confirm',
    'invoice_customer_alias_confirm',
    'supplier_profile_edit_confirm',
    'idle_attachment_accounting_proposal',
    'accounting_document_duplicate_save_decision',
    'accounting_document_category_create_confirm',
)

ACCOUNTING_CATEGORY_PREVIEW_CONTEXTS = (
    'accounting_document_category_preview_decision',
)

ACCOUNTING_CATEGORY_UNKNOWN_CONTEXTS = (
    'accounting_document_category_unknown_decision',
)

ACCOUNTING_CATEGORY_SELECTION_CONTEXTS = (
    'accounting_document_category_selection',
)

ACCOUNTING_CATEGORY_SIMILAR_CONTEXTS = (
    'accounting_document_category_similar_decision',
)

APPROVE_EDIT_CANCEL_CONTEXTS = (
    'invoice_preview_confirmation',
    'invoice_postpdf_decision',
    'accounting_document_intake_preview',
    'customization_request_preview',
    'customization_request_admin_response_preview',
)

GLOBAL_CANCEL_CONTEXTS = (
    'global_state_cancel',
)

YES_NO_CASES = (
    ('ano', 'yes'),
    ('áno', 'yes'),
    ('tak', 'yes'),
    ('ok', 'yes'),
    ('yes', 'yes'),
    ('так', 'yes'),
    ('да', 'yes'),
    ('nie', 'no'),
    ('no', 'no'),
    ('ні', 'no'),
    ('нет', 'no'),
    ('asi', 'unknown'),
    ('random text', 'unknown'),
)

STT_ANO_ARTIFACT_CASES = (
    'Ah, n\u00e3o',
    'Ah no',
    'Ah \u0148ao',
    '\u0410\u0445\u043d\u044f\u043e',
)

APPROVE_EDIT_CANCEL_CASES = (
    ('schvalit', 'approve'),
    ('schváliť', 'approve'),
    ('potvrdit', 'approve'),
    ('potvrď', 'approve'),
    ('ulozit', 'approve'),
    ('uložiť', 'approve'),
    ('ano', 'approve'),
    ('áno', 'approve'),
    ('ok', 'approve'),
    ('tak', 'approve'),
    ('так', 'approve'),
    ('да', 'approve'),
    ('upravit', 'edit'),
    ('upraviť', 'edit'),
    ('edit', 'edit'),
    ('zmenit', 'edit'),
    ('zmeniť', 'edit'),
    ('zrusit', 'cancel'),
    ('zrušiť', 'cancel'),
    ('nie', 'cancel'),
    ('no', 'cancel'),
    ('cancel', 'cancel'),
    ('zahodit', 'cancel'),
    ('zahodiť', 'cancel'),
    ('ні', 'cancel'),
    ('нет', 'cancel'),
    ('asi', 'unknown'),
    ('random text', 'unknown'),
)

_LOCAL_CONFIRMATION_TOKENS = {
    'ano',
    'nie',
    'tak',
    'ok',
    'da',
    'schvalit',
    'upravit',
    'zrusit',
}


@pytest.mark.parametrize('context_name', YES_NO_CONTEXTS)
@pytest.mark.parametrize(('user_input', 'expected'), YES_NO_CASES)
def test_yes_no_context_matrix_exact_mappings(context_name: str, user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize('context_name', APPROVE_EDIT_CANCEL_CONTEXTS)
@pytest.mark.parametrize(('user_input', 'expected'), APPROVE_EDIT_CANCEL_CASES)
def test_approve_edit_cancel_context_matrix_exact_mappings(
    context_name: str,
    user_input: str,
    expected: str,
) -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize('context_name', ACCOUNTING_CATEGORY_PREVIEW_CONTEXTS)
@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('ulozit s kategoriou', 'save_with_category'),
        ('schvalit', 'save_with_category'),
        ('ano', 'save_with_category'),
        ('ok', 'save_with_category'),
        ('zmenit kategoriu', 'change_document_category'),
        ('zmenit kategoriu polozky', 'change_line_item_category'),
        ('ulozit bez kategorie', 'save_without_category'),
        ('zrusit', 'cancel'),
        ('nie', 'cancel'),
        ('random text', 'unknown'),
    ],
)
def test_accounting_category_preview_context_matrix_exact_mappings(
    context_name: str,
    user_input: str,
    expected: str,
) -> None:
    assert asyncio.run(
        resolve_accounting_document_category_preview_decision(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize('context_name', ACCOUNTING_CATEGORY_UNKNOWN_CONTEXTS)
@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('vybrat existujucu kategoriu', 'choose_existing_category'),
        ('vytvorit novu kategoriu', 'create_new_category'),
        ('ulozit ako na kontrolu', 'save_as_unknown_review'),
        ('zrusit', 'cancel'),
        ('random text', 'unknown'),
    ],
)
def test_accounting_category_unknown_context_matrix_exact_mappings(
    context_name: str,
    user_input: str,
    expected: str,
) -> None:
    assert asyncio.run(
        resolve_accounting_document_category_unknown_decision(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize('context_name', ACCOUNTING_CATEGORY_SELECTION_CONTEXTS)
def test_accounting_category_selection_context_matches_id_or_label(context_name: str) -> None:
    allowed_categories = [
        {'category_id': 'materials', 'label_sk': 'Materiál'},
        {'category_id': 'workspace_custom_tools', 'label_sk': 'Moje náradie'},
    ]

    assert asyncio.run(
        resolve_accounting_document_category_selection(
            context_name=context_name,
            user_input_text='Moje naradie',
            allowed_categories=allowed_categories,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'workspace_custom_tools'
    assert asyncio.run(
        resolve_accounting_document_category_selection(
            context_name=context_name,
            user_input_text='materials',
            allowed_categories=allowed_categories,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'materials'


@pytest.mark.parametrize('context_name', ACCOUNTING_CATEGORY_SIMILAR_CONTEXTS)
@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('pouzit existujucu', 'use_existing_category'),
        ('vytvorit novu aj tak', 'create_new_anyway'),
        ('spat', 'back'),
        ('random text', 'unknown'),
    ],
)
def test_accounting_category_similar_context_matrix_exact_mappings(
    context_name: str,
    user_input: str,
    expected: str,
) -> None:
    assert asyncio.run(
        resolve_accounting_document_category_similar_decision(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize('context_name', GLOBAL_CANCEL_CONTEXTS)
@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('/cancel', 'cancel'),
        ('назад', 'cancel'),
        ('cancel', 'cancel'),
        ('zrušiť', 'cancel'),
        ('скасувати', 'cancel'),
        ('відмінити', 'cancel'),
        ('відминити', 'cancel'),
        ('отменить', 'cancel'),
        ('почни з початку', 'cancel'),
        ('random text', 'unknown'),
    ],
)
def test_global_cancel_context_matrix_exact_mappings(
    context_name: str, user_input: str, expected: str
) -> None:
    assert asyncio.run(
        resolve_global_cancel(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize('user_input', ['zrušiť', 'скасувати', 'відмінити', 'назад', 'почни з початку'])
def test_global_cancel_shortcut_filter_comes_from_shared_resolver_layer(user_input: str) -> None:
    assert is_global_cancel_text(user_input) is True


def test_noisy_zrushyty_is_not_deterministic_global_cancel() -> None:
    assert is_global_cancel_text('зрушити') is False


def test_delete_invoice_yes_no_stt_ano_noise_maps_to_yes() -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='delete_existing_invoice_confirm',
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'yes'


@pytest.mark.parametrize('context_name', YES_NO_CONTEXTS)
@pytest.mark.parametrize('user_input', STT_ANO_ARTIFACT_CASES)
def test_yes_no_stt_ano_artifacts_map_to_yes(context_name: str, user_input: str) -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name=context_name,
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'yes'


def test_yes_no_stt_ano_artifacts_bypass_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_openai(*args, **kwargs):
        raise AssertionError('known STT ano artifacts must be handled before LLM fallback')

    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _fail_openai)

    assert asyncio.run(
        resolve_yes_no(
            context_name='contact_confirm',
            user_input_text='Ah no',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'yes'


@pytest.mark.parametrize('user_input', ['Ah non !', 'A non', 'Ah nu'])
def test_customer_alias_yes_no_stt_noise_stays_unknown(user_input: str) -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='invoice_customer_alias_confirm',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_customer_alias_yes_no_stt_noise_does_not_call_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_openai(*args, **kwargs):
        raise AssertionError('ambiguous STT yes/no noise must be handled before LLM fallback')

    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _fail_openai)

    assert asyncio.run(
        resolve_yes_no(
            context_name='invoice_customer_alias_confirm',
            user_input_text='Ah non !',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'unknown'


@pytest.mark.parametrize('context_name', ['invoice_preview_confirmation', 'invoice_postpdf_decision', 'customization_request_preview'])
def test_invoice_approve_edit_cancel_stt_ano_noise_maps_to_approve(context_name: str) -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name=context_name,
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'approve'


@pytest.mark.parametrize('user_input', STT_ANO_ARTIFACT_CASES)
def test_invoice_preview_stt_ano_artifacts_map_to_approve(user_input: str) -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name='invoice_preview_confirmation',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'approve'


def test_invoice_preview_stt_ano_artifacts_bypass_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_openai(*args, **kwargs):
        raise AssertionError('known STT ano artifacts must be handled before LLM fallback')

    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _fail_openai)

    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name='invoice_preview_confirmation',
            user_input_text='Ah no',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'approve'


@pytest.mark.parametrize('context_name', ['contact_confirm', 'idle_attachment_accounting_proposal'])
def test_non_invoice_yes_no_stt_ano_noise_maps_to_yes(context_name: str) -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name=context_name,
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'yes'


@pytest.mark.parametrize('user_input', ['no', 'n\u00f3', 'noo', 'nou'])
def test_standalone_no_variants_are_not_affirmative(user_input: str) -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='contact_confirm',
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) != 'yes'


def _string_literal_values(node: ast.AST) -> set[str]:
    if not isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return set()
    return {element.value for element in node.elts if isinstance(element, ast.Constant) and isinstance(element.value, str)}


def _raw_reply_expression(source: str) -> bool:
    raw_names = ('message.text', 'answer_text', 'decision_text', 'confirmation_text', 'recognized_text')
    return any(name in source for name in raw_names) or '.lower(' in source or '.casefold(' in source


def _has_local_confirmation_parser(path: Path) -> bool:
    source = path.read_text(encoding='utf-8-sig')
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            left_source = ast.get_source_segment(source, node.left) or ''
            for comparator, operator in zip(node.comparators, node.ops):
                literal_values = _string_literal_values(comparator)
                if isinstance(operator, (ast.In, ast.NotIn)) and len(literal_values & _LOCAL_CONFIRMATION_TOKENS) >= 2:
                    return True
                if isinstance(operator, (ast.Eq, ast.NotEq)):
                    right_source = ast.get_source_segment(source, comparator) or ''
                    constant_values = literal_values | (
                        {comparator.value}
                        if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
                        else set()
                    )
                    if constant_values & _LOCAL_CONFIRMATION_TOKENS and _raw_reply_expression(left_source + right_source):
                        return True
    return False


def test_handlers_do_not_define_local_confirmation_parsers() -> None:
    for path in Path('bot/handlers').glob('*.py'):
        assert not _has_local_confirmation_parser(path), (
            'Canonical DecisionResolver contract violation: local confirmation parser found in '
            f'{path}. Use bot/services/decision_resolver.py and register the context in the test matrix.'
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
    'context_name',
    ['invoice_preview_confirmation', 'invoice_postpdf_decision', 'accounting_document_intake_preview', 'customization_request_preview'],
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


def test_yes_no_stt_ano_noise_maps_to_yes_for_idle_attachment_accounting() -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='idle_attachment_accounting_proposal',
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'yes'


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

def test_accounting_category_button_labels_resolve_to_canonical_decisions() -> None:
    assert asyncio.run(
        resolve_accounting_document_category_preview_decision(
            context_name='accounting_document_category_preview_decision',
            user_input_text='✅ Uložiť s kategóriou',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'save_with_category'
    assert asyncio.run(
        resolve_accounting_document_category_unknown_decision(
            context_name='accounting_document_category_unknown_decision',
            user_input_text='📂 Vybrať existujúcu kategóriu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'choose_existing_category'
    assert asyncio.run(
        resolve_accounting_document_category_similar_decision(
            context_name='accounting_document_category_similar_decision',
            user_input_text='➕ Vytvoriť novú aj tak',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_new_anyway'
    assert asyncio.run(
        resolve_yes_no(
            context_name='accounting_document_category_create_confirm',
            user_input_text='✅ Áno',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'yes'

def test_accounting_duplicate_loud_button_labels_resolve_through_yes_no_family() -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='accounting_document_duplicate_save_decision',
            user_input_text='➕ Pridať iný bloček',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'no'
    assert asyncio.run(
        resolve_yes_no(
            context_name='accounting_document_duplicate_save_decision',
            user_input_text='⚠️ Uložiť aj tak',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'yes'
    assert asyncio.run(
        resolve_yes_no(
            context_name='accounting_document_duplicate_save_decision',
            user_input_text='🏠 /menu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'no'