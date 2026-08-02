import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.config import Config
from bot.handlers.invoice import (
    CustomizationRequestStates,
    InvoiceStates,
    _build_customization_request_draft,
    _format_customization_request_preview,
    _normalize_items_input,
    customization_request_edit_text,
    customization_request_preview_decision,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
    process_invoice_service_clarification,
    process_invoice_slot_clarification,
    process_invoice_text,
    semantic_top_level_input,
)
from bot.handlers.work_time import WorkTimeStates
from bot.services.customization_requests import CustomizationRequestService
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.product_truth import list_capabilities
from bot.services.info_help import InfoHelpTriageResult, build_top_level_unknown_guidance
from bot.services.invoice_analytics_planner import InvoiceAnalyticsPlan
from bot.services.safe_python_analytics_executor import AnalyticsCodeValidationError
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.semantic_action_resolver import resolve_bounded_confirmation_reply, resolve_semantic_action


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.message_id = 1
        self.update_id = 1
        self.from_user = None
        self.answers: list[str] = []
        self.documents: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def answer_document(self, document, caption: str | None = None) -> None:
        self.documents.append(caption or '')


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False
        self.data: dict = {}
        self.current_state = None

    async def clear(self) -> None:
        self.cleared = True

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, new_state) -> None:
        self.current_state = new_state

    async def get_data(self) -> dict:
        return dict(self.data)

    async def get_state(self):
        return self.current_state


class _DummyDecisionState:
    def __init__(self) -> None:
        self.data = {'last_invoice_id': 999}
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.cleared = True

    async def get_state(self):
        return None


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def _config_with_api_key(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def _config_with_valid_api_key(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='sk-test',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def _authorized_message(text: str, telegram_id: int = 111) -> _DummyMessage:
    message = _DummyMessage(text)
    message.from_user = type('_User', (), {'id': telegram_id})()
    return message



def test_customization_request_draft_uses_structured_admin_review_fields() -> None:
    draft = _build_customization_request_draft(
        requester_telegram_id=111,
        user_input_text='Can I have two profiles: one SZCO and one company?',
        source_channel='voice',
        triage_class='admin_review_candidate',
        capability_id='unknown',
        topic_id='admin_review',
        confidence=0.86,
        business_need='Používateľ chce samostatné profily pre SZČO a firmu v jednom bote.',
        detected_domain='workspace_setup',
        expected_outcome='Faktúry, kontakty, nastavenia a číslovanie majú byť oddelené podľa aktívneho profilu.',
        clarification_questions=(
            'Má mať každý profil samostatné číslovanie faktúr?',
            'Majú byť kontakty a dokumenty oddelené podľa profilu?',
        ),
        proposed_title='Viac firemných profilov v jednom bote',
        proposed_description='Skontrolovať prepínanie firemných profilov a pracovných priestorov.',
        risk_level='critical',
    )

    assert draft['normalized_title'].endswith('Viac firemných profilov v jednom bote')
    assert draft['detected_domain'] == 'workspace_setup'
    assert draft['risk_level'] == 'critical'
    assert 'Čo používateľ chce: Používateľ chce samostatné profily pre SZČO a firmu v jednom bote.' in draft['normalized_summary']
    assert 'Doména: workspace_setup' in draft['normalized_summary']
    assert 'Má mať každý profil samostatné číslovanie faktúr?' in draft['normalized_summary']
    assert draft['source_capability_id'] is None


def test_customization_request_preview_is_compact_user_facing_slovak() -> None:
    draft = _build_customization_request_draft(
        requester_telegram_id=111,
        user_input_text='Download bank statements from Gmail and save them on Google Drive.',
        source_channel='voice',
        triage_class='admin_review_candidate',
        capability_id='unknown',
        topic_id='admin_review',
        confidence=0.86,
        business_need='Používateľ chce automaticky získavať bankové výpisy z e-mailu a ukladať ich na Google Drive.',
        detected_domain='google_drive',
        expected_outcome='Bankové výpisy majú byť dostupné v cloudovom úložisku a usporiadané na ďalšiu prácu.',
        clarification_questions=(
            'V akom formáte sú bankové výpisy?',
            'Do ktorého priečinka sa majú ukladať?',
        ),
        proposed_title='Automatické získavanie bankových výpisov',
        proposed_description='Skontrolovať požiadavku na automatické získavanie bankových výpisov z Gmailu a ukladanie na Google Drive.',
        risk_level='medium',
    )

    preview = _format_customization_request_preview(draft)

    assert 'Názov: Automatické získavanie bankových výpisov' in preview
    assert 'Chcete automaticky získavať bankové výpisy z e-mailu a ukladať ich na Google Drive.' in preview
    assert 'Očakávaný výsledok: Bankové výpisy majú byť dostupné v cloudovom úložisku' in preview
    assert 'Po potvrdení požiadavku uložím na neskoršiu kontrolu správcom.' in preview
    assert 'Funkciu tým nezapínam ani nič nemením v systéme.' in preview
    assert 'Otázky na upresnenie' not in preview
    assert 'Riziko' not in preview
    assert 'Doména' not in preview
    assert 'What format' not in preview
    assert 'Používateľ chce' not in preview

def test_top_level_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='витворить фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='сделай фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'show_existing_invoice',
                'add_contact',
                'add_service_alias',
                'send_invoice',
                'edit_existing_invoice',
                'edit_invoice',
                'unknown',
            ],
            user_input_text='upraviť fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_existing_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'show_existing_invoice',
                'edit_existing_invoice',
                'delete_existing_invoice',
                'unknown',
            ],
            user_input_text='покажи фактуру номер 04',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'show_existing_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pošli fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'send_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pridaj novú službu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'add_service_alias'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'delete_existing_invoice', 'unknown'],
            user_input_text='delete invoice 02',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_existing_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='blabla',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_top_level_semantic_resolver_system_profile_and_accounting_actions() -> None:
    allowed = [
        'start',
        'create_invoice',
        'show_supplier_profile',
        'edit_supplier',
        'show_recent_accounting_documents',
        'add_receipt',
        'unknown',
    ]

    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='почати',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'start'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='môj profil',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'show_supplier_profile'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='upraviť môj profil',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_supplier'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='покажи останні чеки',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'show_recent_accounting_documents'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='додай, будь ласка, чек',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'add_receipt'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='nahrať prijatú faktúru',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'add_receipt'


def test_top_level_semantic_resolver_does_not_expose_reserved_database_delete() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'unknown'],
            user_input_text='Chcem vymazať moju databázu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_receipt_alias_obeys_allowed_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'unknown'],
            user_input_text='додай, будь ласка, чек',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


@pytest.mark.parametrize(
    'user_input',
    [
        '\u0443\u0434\u0430\u043b\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0443 7',
        '\u0443\u0434\u0430\u043b\u0438\u0442\u044c \u0444\u0430\u043a\u0442\u0443\u0440\u0443 \u043d\u043e\u043c\u0435\u0440 10',
        '\u0432\u0438\u0434\u0430\u043b\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0443 11',
        '\u0432\u044b\u043c\u0430\u0436\u044c \u0444\u0430\u043a\u0442\u0443\u0440\u0443 \u0447\u0438\u0441\u043b\u0430 7',
        'vyma\u017e fakturu cislo 10',
        'VIMA\u0160 FAKTURU \u010cISLO 11',
    ],
)
def test_top_level_delete_invoice_stt_variants_beat_create_invoice(user_input: str) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'add_contact',
                'add_service_alias',
                'send_invoice',
                'edit_existing_invoice',
                'delete_existing_invoice',
                'edit_invoice',
                'unknown',
            ],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_existing_invoice'


def test_top_level_delete_invoice_priority_runs_before_llm_when_key_is_configured() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'edit_existing_invoice',
                'delete_existing_invoice',
                'unknown',
            ],
            user_input_text='\u0443\u0434\u0430\u043b\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0443 10',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'delete_existing_invoice'


def test_top_level_polite_add_receipt_uses_bounded_resolver_when_key_is_configured(monkeypatch) -> None:
    _TopLevelActionOpenAIFake.canonical_action = 'add_receipt'
    _TopLevelActionOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _TopLevelActionOpenAIFake)

    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_receipt', 'unknown'],
            user_input_text='додай, будь ласка, чек',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'add_receipt'
    payload = _TopLevelActionOpenAIFake.last_payload
    assert payload is not None
    assert payload['allowed_actions'] == ['add_receipt', 'create_invoice', 'unknown']


def test_invoice_create_not_misrouted_to_add_contact_when_company_mentioned() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre company ZS',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'


def test_top_level_edit_existing_invoice_short_reference_beats_create_invoice() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'edit_existing_invoice', 'edit_invoice', 'unknown'],
            user_input_text='Uprav faktúru 15',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_existing_invoice'


@pytest.mark.parametrize(
    ('user_input', 'expected_action'),
    [
        ('покажи фактуру 04', 'show_existing_invoice'),
        ('upraviť fakturu 05', 'edit_existing_invoice'),
        ('покажи видатки за цей рік', 'unknown'),
    ],
)
def test_smoke_nearby_invoice_top_actions_stay_out_of_invoice_analytics(
    user_input: str,
    expected_action: str,
) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'invoice_period_summary',
                'invoice_analytics',
                'show_existing_invoice',
                'edit_existing_invoice',
                'show_recent_accounting_documents',
                'unknown',
            ],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected_action


def test_pdf_template_question_does_not_resolve_to_invoice_edit_action() -> None:
    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'edit_existing_invoice', 'edit_invoice', 'unknown'],
            user_input_text='Môžem si upraviť PDF šablónu?',
            api_key=None,
            model='gpt-4o',
        )
    )

    assert result == 'unknown'


def test_generic_urob_mi_to_does_not_create_invoice_without_target() -> None:
    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'unknown'],
            user_input_text='urob mi to',
            api_key=None,
            model='gpt-4o',
        )
    )

    assert result == 'unknown'


def test_send_invoice_request_does_not_become_invoice_creation() -> None:
    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'send_invoice', 'unknown'],
            user_input_text='Po\u0161li fakt\u00faru 12',
            api_key=None,
            model='gpt-4o',
        )
    )

    assert result == 'send_invoice'


YEARLY_INVOICE_ANALYTICS_INPUTS = [
        'Na akú sumu som vystavil faktúry v tomto roku?',
        'Koľko som vystavil faktúr tento rok?',
        'Súhrn faktúr za 2026',
        'На яку суму я виставив фактур цього року?',
        'Скільки фактур я виставив за цей рік?',
        'На яку суму я вже виставив фактуру в цьому році?',
        'На какую сумму я выставил фактур в этом году?',
        'На якую суму я выставіў фактур у гэтым годзе?',
]


def test_process_invoice_text_answers_invoice_period_summary_without_side_effects(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    invoice_service = InvoiceService(config.db_path)
    invoice_service.create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        invoice_number='20260001',
        issue_date='2026-01-15',
        delivery_date='2026-01-15',
        due_date='2026-01-29',
        due_days=14,
        total_amount=100.25,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='oprava',
                description_normalized='Oprava',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=100.25,
                total_price=100.25,
            )
        ],
    )
    invoice_service.create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        invoice_number='20260002',
        issue_date='2026-06-01',
        delivery_date='2026-06-01',
        due_date='2026-06-15',
        due_days=14,
        total_amount=200,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='servis',
                description_normalized='Servis',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=200,
                total_price=200,
            )
        ],
    )
    invoice_service.create_invoice_with_items(
        supplier_telegram_id=222,
        contact_id=1,
        invoice_number='20260001',
        issue_date='2026-06-01',
        delivery_date='2026-06-01',
        due_date='2026-06-15',
        due_days=14,
        total_amount=999,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='cudzia',
                description_normalized='Cudzia',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=999,
                total_price=999,
            )
        ],
    )

    message = _authorized_message('На яку суму я виставив фактур цього року?', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.cleared is True
    assert state.current_state is None
    assert 'Súhrn vystavených faktúr za aktuálny rok 2026' in message.answers[-1]
    assert 'Počet faktúr: 2' in message.answers[-1]
    assert 'Celkom: 300.25 EUR' in message.answers[-1]
    assert '999.00' not in message.answers[-1]
    assert message.documents == []
    assert not (tmp_path / 'invoices').exists()


def test_invoice_period_summary_uses_bounded_period_value_resolver(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict] = []

    async def _resolver(**kwargs) -> str:
        calls.append(kwargs)
        if kwargs['context_name'] == 'top_level_action':
            return 'invoice_analytics'
        if kwargs['context_name'] == 'invoice_analytics_execution_strategy':
            assert kwargs['allowed_actions'] == ['whole_calendar_year_summary', 'safe_analytics_runtime', 'unknown']
            assert 'whole_calendar_year_summary' in kwargs['action_hints']
            assert 'safe_runtime_examples' in kwargs['auxiliary_context']
            return 'whole_calendar_year_summary'
        if kwargs['context_name'] == 'invoice_summary_period_selection':
            assert kwargs['allowed_actions'] == ['current_year', 'previous_year', 'unknown']
            assert 'current_year' in kwargs['action_hints']
            assert 'supported_periods' in kwargs['auxiliary_context']
            return 'current_year'
        return 'unknown'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    config = _config_with_valid_api_key(tmp_path)
    message = _authorized_message('На яку суму я виставив фактур цього року?', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert [call['context_name'] for call in calls] == [
        'top_level_action',
        'invoice_analytics_execution_strategy',
        'invoice_summary_period_selection',
    ]
    assert 'Za aktuálny rok 2026 som vo vašom účte nenašiel žiadne vystavené faktúry.' in message.answers[-1]
    assert not config.db_path.exists()


def test_process_invoice_text_invoice_period_summary_without_db_does_not_create_db(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _authorized_message('Súhrn faktúr za 2026', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert 'Za rok 2026 som vo vašom účte nenašiel žiadne vystavené faktúry.' in message.answers[-1]
    assert state.cleared is True
    assert not config.db_path.exists()


def test_process_invoice_text_month_invoice_question_does_not_use_yearly_fallback(tmp_path: Path) -> None:
    message = _authorized_message('Koľko bolo faktúr minulý mesiac?', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text=message.text))

    assert 'Zatiaľ viem spočítať vystavené faktúry za kalendárny rok' not in message.answers[-1]
    assert 'uložené vystavené faktúry na analýzu' in message.answers[-1]
    assert state.cleared is True


def test_process_invoice_text_quarter_invoice_question_uses_safe_analytics_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[dict] = []

    async def _resolver(**kwargs) -> str:
        calls.append(kwargs)
        if kwargs['context_name'] == 'top_level_action':
            return 'invoice_analytics'
        if kwargs['context_name'] == 'invoice_analytics_execution_strategy':
            assert 'whole_calendar_year_summary' in kwargs['allowed_actions']
            assert 'safe_analytics_runtime' in kwargs['allowed_actions']
            return 'safe_analytics_runtime'
        return 'unknown'

    async def _unexpected_planner(**kwargs) -> InvoiceAnalyticsPlan:
        raise AssertionError('planner must not run for empty dataset')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _unexpected_planner)

    message = _authorized_message('На яку суму я виставив фактури за перший квартал 2026?', telegram_id=111)
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_valid_api_key(tmp_path),
            invoice_text=message.text,
        )
    )

    assert [call['context_name'] for call in calls] == [
        'top_level_action',
        'invoice_analytics_execution_strategy',
    ]
    assert 'Súhrn vystavených faktúr za rok 2026' not in message.answers[-1]
    assert 'uložené vystavené faktúry na analýzu' in message.answers[-1]
    assert state.cleared is True


@pytest.mark.parametrize(
    'user_input',
    [
        'Porovnaj vystavené faktúry za február a apríl 2026.',
        'Koľko som vyfakturoval za druhý kvartál 2026?',
        'Скільки було виставлених фактур за останні 90 днів?',
    ],
)
def test_smoke_invoice_analytics_new_questions_reach_safe_runtime(
    tmp_path: Path,
    monkeypatch,
    user_input: str,
) -> None:
    config = _config_with_valid_api_key(tmp_path)
    init_db(config.db_path)
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        invoice_number='20260021',
        issue_date='2026-04-12',
        delivery_date='2026-04-12',
        due_date='2026-04-26',
        due_days=14,
        total_amount=420,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='servis',
                description_normalized='Servis',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=420,
                total_price=420,
            )
        ],
    )
    resolver_calls: list[dict] = []
    planner_calls: list[dict] = []

    async def _resolver(**kwargs) -> str:
        resolver_calls.append(kwargs)
        if kwargs['context_name'] == 'top_level_action':
            return 'invoice_analytics'
        if kwargs['context_name'] == 'invoice_analytics_execution_strategy':
            return 'safe_analytics_runtime'
        return 'unknown'

    async def _planner(**kwargs) -> InvoiceAnalyticsPlan:
        planner_calls.append(kwargs)
        assert kwargs['user_question'] == user_input
        assert kwargs['repair_feedback'] is None
        return InvoiceAnalyticsPlan(
            analysis_code=(
                'df = invoices_df.copy()\n'
                'result = {"summary": {"invoice_count": int(len(df)), "total": float(df["total_amount"].sum())}, '
                '"tables": {}, "warnings": [], "answer_hints": []}'
            ),
            answer_language='sk',
            reasoning_summary='safe smoke runtime plan',
        )

    def _execute(**kwargs):
        assert 'current_date' in kwargs
        return SimpleNamespace(
            result={'summary': {'invoice_count': 1, 'total': 420.0}, 'tables': {}, 'warnings': [], 'answer_hints': []},
            warnings=(),
        )

    async def _answer(**kwargs) -> str:
        assert kwargs['user_question'] == user_input
        assert kwargs['answer_language'] == 'sk'
        assert kwargs['computed_result']['summary'] == {'invoice_count': 1, 'total': 420.0}
        return 'Za zadané obdobie evidujem 1 vystavenú faktúru v sume 420.00 EUR.'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _planner)
    monkeypatch.setattr('bot.handlers.invoice.execute_invoice_analytics_code', _execute)
    monkeypatch.setattr('bot.handlers.invoice.answer_invoice_analytics', _answer)

    message = _authorized_message(user_input, telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert [call['context_name'] for call in resolver_calls] == [
        'top_level_action',
        'invoice_analytics_execution_strategy',
    ]
    assert len(planner_calls) == 1
    assert message.answers[-1] == 'Za zadané obdobie evidujem 1 vystavenú faktúru v sume 420.00 EUR.'
    assert 'kalendárny rok' not in message.answers[-1]
    assert state.cleared is True


def test_process_invoice_text_routes_add_service_alias_to_existing_service_flow(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('pridaj novú službu')
    state = _DummyState()
    calls: list[str] = []

    async def _resolver(**kwargs):
        return 'add_service_alias'

    async def _start_service(**kwargs) -> None:
        calls.append('service_flow')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_add_service_alias_intake', _start_service)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='pridaj novú službu',
        )
    )

    assert calls == ['service_flow']
    assert message.answers == []


def test_process_invoice_text_routes_system_and_profile_actions_to_existing_flows(tmp_path: Path, monkeypatch) -> None:
    routed: list[str] = []

    async def _start(**kwargs) -> None:
        routed.append('start')

    async def _profile(**kwargs) -> None:
        routed.append('profile')

    async def _edit_profile(**kwargs) -> None:
        routed.append('edit_profile')

    async def _recent(**kwargs) -> None:
        routed.append('recent')

    monkeypatch.setattr('bot.handlers.invoice.cmd_start', _start)
    monkeypatch.setattr('bot.handlers.invoice.cmd_moj_profil', _profile)
    monkeypatch.setattr('bot.handlers.invoice.cmd_upravit_profil', _edit_profile)
    monkeypatch.setattr('bot.handlers.invoice.cmd_blocky', _recent)

    for text in ('start', 'môj profil', 'upraviť môj profil', 'posledné bločky'):
        message = _DummyMessage(text)
        state = _DummyState()
        asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text=text))

    assert routed == ['start', 'profile', 'edit_profile', 'recent']


def test_process_invoice_text_passes_domain_context_for_profile_rekvizity(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}
    routed: list[str] = []

    async def _resolver(**kwargs):
        captured.update(kwargs)
        return 'show_supplier_profile'

    async def _profile(**kwargs) -> None:
        routed.append('profile')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.cmd_moj_profil', _profile)

    asyncio.run(
        process_invoice_text(
            message=_DummyMessage('Мої реквізити'),
            state=_DummyState(),
            config=_config(tmp_path),
            invoice_text='Мої реквізити',
        )
    )

    assert routed == ['profile']
    assert captured['user_input_text'] == 'Мої реквізити'
    profile_hint = captured['action_hints']['show_supplier_profile']['meaning']
    assert 'billing details' in profile_hint
    assert 'fakturačné údaje dodávateľa' in profile_hint
    assert 'firemné údaje' in profile_hint
    assert 'positive_examples' not in captured['action_hints']['show_supplier_profile']
    assert 'edit or change supplier/company/profile/billing details' in captured['action_hints']['show_supplier_profile']['not_this']


def test_active_fsm_top_level_text_is_not_executed_from_generic_router(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []

    async def _unexpected_process_invoice_text(**kwargs) -> None:
        calls.append(str(kwargs.get('invoice_text')))

    monkeypatch.setattr('bot.handlers.invoice.process_invoice_text', _unexpected_process_invoice_text)
    state = _DummyState()
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(semantic_top_level_input(_DummyMessage('vytvor faktúru'), state, _config(tmp_path)))

    assert calls == []


def test_process_invoice_text_routes_add_receipt_to_existing_upload_flow_without_invoice(tmp_path: Path) -> None:
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates

    config = _config(tmp_path)
    message = _DummyMessage('додай, будь ласка, чек')
    message.from_user = type('_User', (), {'id': 111})()
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text='додай, будь ласка, чек',
        )
    )

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload
    assert 'fotku alebo PDF' in message.answers[-1]
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_process_invoice_text_edit_existing_invoice_by_short_number(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    SupplierService(config.db_path).create_or_replace(
        SupplierProfile(
            telegram_id=111,
            name='S',
            ico='1',
            dic='1',
            ic_dph='',
            address='A',
            iban='SK1',
            swift='ABCD',
            email='a@a.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    invoice_id = InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        issue_date='2026-04-30',
        delivery_date='2026-04-30',
        due_date='2026-05-14',
        due_days=14,
        total_amount=10,
        currency='EUR',
        status='draft',
        items=[CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)],
        invoice_number='20260015',
    )
    message = _DummyMessage('upraviť faktúru 15')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    calls: list[int] = []

    async def _resolver(**kwargs):
        return 'edit_existing_invoice'

    async def _start_edit(**kwargs):
        calls.append(kwargs['invoice_id'])

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_invoice_edit_flow', _start_edit)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert calls == [invoice_id]
    preview = message.answers[0]
    assert 'Číslo faktúry: 20260015' in preview
    assert 'Dátum vystavenia: 2026-04-30' in preview
    assert 'Dátum dodania: 2026-04-30' in preview
    assert 'Dátum splatnosti: 2026-05-14' in preview
    assert 'x' in preview
    assert 'Množstvo: 1 ks × 10.00 EUR = 10.00 EUR' in preview
    assert 'Celkom: 10.00 EUR' in preview


def test_process_invoice_text_show_existing_invoice_is_read_only_and_clears_state(
    tmp_path: Path, monkeypatch
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    SupplierService(config.db_path).create_or_replace(
        SupplierProfile(
            telegram_id=111,
            name='S',
            ico='1',
            dic='1',
            ic_dph='',
            address='A',
            iban='SK1',
            swift='ABCD',
            email='a@a.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    invoice_id = InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        issue_date='2026-04-30',
        delivery_date='2026-04-30',
        due_date='2026-05-14',
        due_days=14,
        total_amount=10,
        currency='EUR',
        status='draft',
        items=[
            CreateInvoiceItemPayload(
                description_raw='x',
                description_normalized='x',
                item_description_raw='',
                quantity=1,
                unit='ks',
                unit_price=10,
                total_price=10,
            )
        ],
        invoice_number='20260004',
    )
    message = _DummyMessage('покажи фактуру 04')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    calls: list[int] = []

    async def _resolver(**kwargs):
        return 'show_existing_invoice'

    async def _start_edit(**kwargs):
        calls.append(kwargs['invoice_id'])

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_invoice_edit_flow', _start_edit)

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert calls == []
    assert state.cleared is True
    assert InvoiceService(config.db_path).get_invoice_by_id(invoice_id) is not None
    assert 'Číslo faktúry: 20260004' in message.answers[0]
    assert 'Celkom: 10.00 EUR' in message.answers[0]


def test_process_invoice_text_top_level_hints_disambiguate_work_time_delete_from_invoice_delete(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}

    async def _resolver(**kwargs):
        captured.update(kwargs)
        return 'unknown'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('видали dochadzku')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    hints = captured['action_hints']
    assert 'видали dochadzku' in hints['delete_work_time_month']['positive_examples']
    assert any('dochadzka' in item for item in hints['delete_existing_invoice']['not_this'])
    assert 'delete_work_time_month' in captured['allowed_actions']
    assert 'delete_existing_invoice' in captured['allowed_actions']


def test_process_invoice_text_top_level_work_time_report_hint_uses_positive_examples(tmp_path: Path, monkeypatch) -> None:
    captured: dict = {}

    async def _resolver(**kwargs):
        captured.update(kwargs)
        return 'unknown'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('Покажи мені табель працівного часу.')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    hints = captured['action_hints']
    report_hint = hints['generate_work_time_report']
    assert 'positive_examples' in report_hint
    assert 'Покажи табель рабочего времени' in report_hint['positive_examples']
    assert 'timesheet report' in report_hint['meaning']
    assert 'delete stored work-time records' in report_hint['not_this']
    assert 'generate_work_time_report' in captured['allowed_actions']

def test_process_invoice_text_passes_llm_report_period_slot_to_work_time(tmp_path: Path, monkeypatch) -> None:
    captured_resolver: dict = {}
    captured_report: dict = {}

    async def _resolver(**kwargs):
        captured_resolver.update(kwargs)
        diagnostics = kwargs.get('diagnostics')
        if isinstance(diagnostics, dict):
            diagnostics['slots'] = {'period': {'type': 'month', 'year': None, 'month': 5}}
        return 'generate_work_time_report'

    async def _start_report(**kwargs):
        captured_report.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_generate_work_time_report', _start_report)
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('покажи табель рабочего времени за May')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert captured_resolver['auxiliary_context']['business_timezone'] == 'Europe/Bratislava'
    assert captured_resolver['action_hints']['generate_work_time_report']['slots']['period']
    assert captured_report['report_period'] == {'type': 'month', 'year': None, 'month': 5}

def test_process_invoice_text_mixed_dochadzka_delete_routes_to_work_time_not_invoice(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('видали dochadzku')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == WorkTimeStates.waiting_delete_month_input
    assert 'Za ktory mesiac' in message.answers[-1]
    assert 'faktúry' not in message.answers[-1].lower()

def test_process_invoice_text_delete_existing_invoice_ambiguous_suffix(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    SupplierService(config.db_path).create_or_replace(
        SupplierProfile(telegram_id=111, name='S', ico='1', dic='1', ic_dph='', address='A', iban='SK1', swift='ABCD', email='a@a.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14)
    )
    service = InvoiceService(config.db_path)
    for num in ('20260002', '20261002'):
        service.create_invoice_with_items(
            supplier_telegram_id=111, contact_id=1, issue_date='2026-04-30', delivery_date='2026-04-30', due_date='2026-05-14', due_days=14,
            total_amount=10, currency='EUR', status='draft',
            items=[CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)],
            invoice_number=num,
        )
    message = _DummyMessage('vymazať faktúru 2')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()

    async def _resolver(**kwargs):
        return 'delete_existing_invoice'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert message.answers[-1] == 'Našiel som viac faktúr. Napíšte viac posledných číslic alebo celé číslo faktúry.'


def test_process_invoice_text_edit_existing_invoice_ambiguity_and_supplier_scope(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = InvoiceService(config.db_path)
    SupplierService(config.db_path).create_or_replace(SupplierProfile(telegram_id=111, name='S1', ico='1', dic='1', ic_dph='', address='A', iban='SK1', swift='ABCD', email='a@a.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14))
    SupplierService(config.db_path).create_or_replace(SupplierProfile(telegram_id=222, name='S2', ico='2', dic='2', ic_dph='', address='B', iban='SK2', swift='EFGH', email='b@b.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14))
    item = CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)
    common = dict(contact_id=1, issue_date='2026-04-30', delivery_date='2026-04-30', due_date='2026-05-14', due_days=14, total_amount=10, currency='EUR', status='draft', items=[item])
    service.create_invoice_with_items(supplier_telegram_id=111, invoice_number='20250015', **common)
    service.create_invoice_with_items(supplier_telegram_id=111, invoice_number='20260015', **common)
    service.create_invoice_with_items(supplier_telegram_id=222, invoice_number='20270015', **common)
    message = _DummyMessage('upraviť faktúru 15')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    async def _resolver(**kwargs):
        return 'edit_existing_invoice'
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert message.answers[-1] == 'Našiel som viac faktúr. Napíšte celé číslo faktúry.'


def test_edit_existing_invoice_missing_pdf_does_not_fail(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = InvoiceService(config.db_path)
    SupplierService(config.db_path).create_or_replace(SupplierProfile(telegram_id=111, name='S1', ico='1', dic='1', ic_dph='', address='A', iban='SK1', swift='ABCD', email='a@a.com', smtp_host=None, smtp_user=None, smtp_pass=None, days_due=14))
    item = CreateInvoiceItemPayload(description_raw='x', description_normalized='x', item_description_raw='', quantity=1, unit='ks', unit_price=10, total_price=10)
    invoice_id = service.create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        issue_date='2026-04-30',
        delivery_date='2026-04-30',
        due_date='2026-05-14',
        due_days=14,
        total_amount=10,
        currency='EUR',
        status='draft',
        items=[item],
        invoice_number='20260015',
    )
    service.save_pdf_path(invoice_id, str(tmp_path / 'missing.pdf'))
    message = _DummyMessage('upraviť faktúru 15')
    message.from_user = type('U', (), {'id': 111})()
    state = _DummyState()
    called: list[int] = []
    async def _resolver(**kwargs):
        return 'edit_existing_invoice'
    async def _start_edit(**kwargs):
        called.append(kwargs['invoice_id'])
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_invoice_edit_flow', _start_edit)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    assert called == [invoice_id]
    assert message.documents == []


def test_state_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='potvrdzujem',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='cancel',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'nie'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_postpdf_decision',
            allowed_actions=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='подтвердить',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


def test_bounded_confirmation_resolver_maps_known_stt_ano_noise() -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='delete_existing_invoice_confirm',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


def test_bounded_confirmation_resolver_positive_regressions() -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='áno',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='нет',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'nie'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='schváliť',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('Так.', 'ano'),
        ('Да.', 'ano'),
        ('Ні.', 'nie'),
        ('Нет.', 'nie'),
        ('Ah, não.', 'ano'),
        ('Ah, não!', 'ano'),
    ],
)
def test_preview_bounded_confirmation_multilingual_and_noisy_inputs(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('schváliť', 'schvalit'),
        ('upraviť', 'upravit'),
        ('zrušiť', 'zrusit'),
        ('Удалить.', 'zrusit'),
        ('delete', 'unknown'),
        ('отменить', 'zrusit'),
        ('зрушити', 'zrusit'),
        ('зрушить', 'zrusit'),
    ],
)
def test_postpdf_bounded_confirmation_multilingual_synonyms(user_input: str, expected: str) -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected


@pytest.mark.parametrize(
    'user_input',
    [
        'Добре уложити зміни, зберегти.',
        'Нічого не треба редагувати. Я хочу, щоб ти зберіг те, що ми вже змінили.',
        'сохрани изменения',
        'uložiť zmeny',
        'uloz zmeny',
        'save changes',
    ],
)
def test_postpdf_save_changes_markers_are_approved_locally(user_input: str) -> None:
    diagnostics: dict[str, str | bool | None] = {}

    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    ) == 'schvalit'
    assert diagnostics['fallback_used'] is True
    assert diagnostics['fallback_output'] == 'schvalit'


def test_postpdf_save_marker_cannot_be_overridden_by_llm(monkeypatch) -> None:
    calls: list[str] = []

    class _WrongSaveOpenAIFake:
        def __init__(self, *, api_key: str) -> None:
            calls.append(api_key)
            self.chat = type('_Chat', (), {'completions': self})()

        async def create(self, **kwargs):
            return _FakeResponse('{"canonical":"upravit"}')

    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _WrongSaveOpenAIFake)
    diagnostics: dict[str, str | bool | None] = {}

    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='Добре уложити зміни, зберегти.',
            api_key='sk-test',
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    ) == 'schvalit'
    assert calls == []
    assert diagnostics['fallback_used'] is True
    assert diagnostics['fallback_output'] == 'schvalit'


@pytest.mark.parametrize(
    'user_input',
    [
        'збережи або відредагуй',
        'uloz alebo uprav',
        'save or cancel',
    ],
)
def test_postpdf_conflicting_local_markers_are_unknown(user_input: str) -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type('_Msg', (), {'content': content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _BoundedResolverOpenAIFake:
    last_messages: list[dict] | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _BoundedResolverOpenAIFake.last_messages = kwargs['messages']
        payload = json.loads(kwargs['messages'][1]['content'])
        text = payload['user_input_text']
        reply_type = payload['expected_reply_type']
        normalized = text.lower().strip()

        if reply_type == 'yes_no_confirmation':
            if normalized in {'ano', 'áno', 'так.', 'да.', 'tak.', 'yes.', 'а-а-а-но'}:
                return _FakeResponse('{"canonical":"ano"}')
            if normalized in {'nie', 'ні.', 'нет.', 'неа.', 'не.'}:
                return _FakeResponse('{"canonical":"nie"}')
            return _FakeResponse('{"canonical":"unknown"}')

        if reply_type == 'postpdf_decision':
            if normalized in {'schváliť', 'подтвердить', 'save it'}:
                return _FakeResponse('{"canonical":"schvalit"}')
            if normalized in {'upraviť', 'исправить', 'change invoice'}:
                return _FakeResponse('{"canonical":"upravit"}')
            if normalized in {
                'zrušiť',
                'видалити фактуру',
                'удалить',
                'выдалить',
                'выдалите фактуру',
                'cancel invoice',
                'remove invoice draft',
                'discard this invoice',
            }:
                return _FakeResponse('{"canonical":"zrusit"}')
            return _FakeResponse('{"canonical":"unknown"}')

        return _FakeResponse('{"canonical":"unknown"}')


class _TopLevelActionOpenAIFake:
    last_payload: dict | None = None
    last_system_prompt: str | None = None
    canonical_action = 'show_recent_accounting_documents'

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _TopLevelActionOpenAIFake.last_system_prompt = kwargs['messages'][0]['content']
        _TopLevelActionOpenAIFake.last_payload = json.loads(kwargs['messages'][1]['content'])
        return _FakeResponse(json.dumps({'canonical_action': _TopLevelActionOpenAIFake.canonical_action}))


class _InfoHelpTriageOpenAIFake:
    output = '{"capability_id":"unknown","topic_id":"unknown","triage_class":"unknown","confidence":0,"needs_clarification":false}'
    last_payload: dict | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _InfoHelpTriageOpenAIFake.last_payload = json.loads(kwargs['messages'][1]['content'])
        return _FakeResponse(_InfoHelpTriageOpenAIFake.output)


class _InventedTopLevelActionOpenAIFake:
    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        return _FakeResponse('{"canonical_action":"delete_user_database"}')


def test_top_level_natural_phrase_uses_bounded_resolver_payload(monkeypatch) -> None:
    _TopLevelActionOpenAIFake.canonical_action = 'show_recent_accounting_documents'
    _TopLevelActionOpenAIFake.last_payload = None
    _TopLevelActionOpenAIFake.last_system_prompt = None
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _TopLevelActionOpenAIFake)

    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['show_recent_accounting_documents', 'add_receipt', 'unknown'],
            user_input_text='prosím zobraz mi posledné doklady z nákupov',
            api_key='sk-test',
            model='gpt-4o',
            action_hints={
                'show_recent_accounting_documents': {
                    'meaning': 'view recent confirmed accounting documents',
                    'not_this': ['upload a new receipt'],
                },
            },
        )
    )

    assert result == 'show_recent_accounting_documents'
    payload = _TopLevelActionOpenAIFake.last_payload
    assert payload is not None
    assert payload['allowed_actions'] == ['add_receipt', 'show_recent_accounting_documents', 'unknown']
    assert payload['expected_output'] == {
        'canonical_action': 'one allowed token or unknown',
        'slots': 'optional object only when requested by action_hints',
    }
    assert 'show_recent_accounting_documents' in payload['action_hints']
    assert 'internally normalize it to Slovak FakturaBot product semantics' in (
        _TopLevelActionOpenAIFake.last_system_prompt or ''
    )
    assert 'Apply action_hints boundaries before positive examples' in (
        _TopLevelActionOpenAIFake.last_system_prompt or ''
    )


def test_top_level_profile_rekvizity_uses_llm_slovak_domain_normalization(monkeypatch) -> None:
    _TopLevelActionOpenAIFake.canonical_action = 'show_supplier_profile'
    _TopLevelActionOpenAIFake.last_payload = None
    _TopLevelActionOpenAIFake.last_system_prompt = None
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _TopLevelActionOpenAIFake)

    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['show_supplier_profile', 'edit_supplier', 'unknown'],
            user_input_text='Мої реквізити',
            api_key='sk-test',
            model='gpt-4o',
            action_hints={
                'show_supplier_profile': {
                    'meaning': (
                        'view supplier/company profile data used on invoices in Slovak FakturaBot context: '
                        'fakturačné údaje dodávateľa, firemné údaje, business identifiers, bank/payment details'
                    ),
                    'not_this': ['edit or change those details'],
                },
                'edit_supplier': {
                    'meaning': 'change supplier/company profile data or billing details',
                    'not_this': ['view profile summary only'],
                },
            },
        )
    )

    assert result == 'show_supplier_profile'
    payload = _TopLevelActionOpenAIFake.last_payload
    assert payload is not None
    assert payload['user_input_text'] == 'Мої реквізити'
    assert 'fakturačné údaje dodávateľa' in payload['action_hints']['show_supplier_profile']['meaning']
    assert 'internally normalize it to Slovak FakturaBot product semantics' in (
        _TopLevelActionOpenAIFake.last_system_prompt or ''
    )


def test_top_level_bounded_resolver_rejects_invented_action(monkeypatch) -> None:
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _InventedTopLevelActionOpenAIFake)

    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['show_recent_accounting_documents', 'add_receipt', 'unknown'],
            user_input_text='prosím urob niečo nejasné',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'unknown'


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('ano', 'ano'),
        ('áno', 'ano'),
        ('Так.', 'ano'),
        ('Да.', 'ano'),
        ('Tak.', 'ano'),
        ('Yes.', 'ano'),
        ('А-а-а-но', 'ano'),
        ('nie', 'nie'),
        ('Ні.', 'nie'),
        ('Нет.', 'nie'),
        ('Неа.', 'nie'),
        ('Не.', 'nie'),
        ('... ??', 'unknown'),
    ],
)
def test_preview_confirmation_llm_contract_handles_multilingual_intent(monkeypatch, user_input: str, expected: str) -> None:
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _BoundedResolverOpenAIFake)

    diagnostics: dict[str, str | bool | None] = {}
    result = asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text=user_input,
            api_key='sk-test',
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    )

    assert result == expected
    if diagnostics['fallback_used']:
        assert diagnostics['fallback_output'] == expected
        return
    system_prompt = _BoundedResolverOpenAIFake.last_messages[0]['content']
    user_payload = json.loads(_BoundedResolverOpenAIFake.last_messages[1]['content'])
    assert 'bounded intent normalizer' in system_prompt
    assert 'user is NOT required to say exact "ano"/"nie"' in system_prompt
    assert user_payload['normalization_contract']['mode'] == 'semantic_intent_first'


@pytest.mark.parametrize(
    ('user_input', 'expected'),
    [
        ('schváliť', 'schvalit'),
        ('подтвердить', 'schvalit'),
        ('save it', 'schvalit'),
        ('upraviť', 'upravit'),
        ('исправить', 'upravit'),
        ('change invoice', 'upravit'),
        ('zrušiť', 'zrusit'),
        ('видалити фактуру', 'zrusit'),
        ('удалить', 'zrusit'),
        ('Выдалить', 'zrusit'),
        ('Выдалите фактуру', 'zrusit'),
        ('cancel invoice', 'zrusit'),
        ('remove invoice draft', 'zrusit'),
        ('discard this invoice', 'zrusit'),
        ('random noise', 'unknown'),
    ],
)
def test_postpdf_confirmation_llm_contract_normalizes_delete_intent(monkeypatch, user_input: str, expected: str) -> None:
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _BoundedResolverOpenAIFake)

    diagnostics: dict[str, str | bool | None] = {}
    result = asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text=user_input,
            api_key='sk-test',
            model='gpt-4o',
            diagnostics=diagnostics,
        )
    )

    assert result == expected
    if diagnostics['fallback_used']:
        assert diagnostics['fallback_output'] == expected
        return
    system_prompt = _BoundedResolverOpenAIFake.last_messages[0]['content']
    user_payload = json.loads(_BoundedResolverOpenAIFake.last_messages[1]['content'])
    assert 'delete/cancel/remove/discard invoice-draft intent to zrusit' in system_prompt
    assert user_payload['normalization_contract']['context_rules']['postpdf_decision'][
        'delete_cancel_remove_discard_invoice_draft'
    ] == 'zrusit_if_allowed'


def test_unknown_top_level_gets_info_help_guidance(tmp_path: Path) -> None:
    message = _DummyMessage('blabla')
    state = _DummyState()
    asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text='blabla'))
    assert state.cleared is True
    assert 'Nerozumiem, čo chcete spraviť.' in message.answers[-1]
    assert 'vytvoriť faktúru' in message.answers[-1]
    assert 'spočítať súhrn vystavených faktúr za kalendárny rok' in message.answers[-1]
    assert 'súhrn faktúr za 2026' in message.answers[-1]
    assert 'pridaj bloček' in message.answers[-1]


GENERAL_INVOICE_ANALYTICS_INPUTS = [
        'Покажи фактури за травень',
        'На яку суму я виставив фактури в березні та травні?',
        'Koľko som vystavil faktúr v marci a máji?',
        'Porovnaj faktúry za marec a máj.',
        'Сума фактур по місяцях.',
        'Порівняй травень 2026 і травень 2025',
        'Koľko mám neuhradených faktúr?',
        'Top klientov podľa sumy faktúr',
]

@pytest.mark.contract
@pytest.mark.regression
@pytest.mark.parametrize(
    'user_input',
    [
        pytest.param(YEARLY_INVOICE_ANALYTICS_INPUTS[0], id='yearly-sk-total-current-year'),
        pytest.param(YEARLY_INVOICE_ANALYTICS_INPUTS[1], id='yearly-sk-count-current-year'),
        pytest.param(YEARLY_INVOICE_ANALYTICS_INPUTS[2], id='yearly-sk-summary-explicit-year'),
        pytest.param(YEARLY_INVOICE_ANALYTICS_INPUTS[3], id='yearly-uk-total-current-year'),
        pytest.param(YEARLY_INVOICE_ANALYTICS_INPUTS[4], id='yearly-uk-count-current-year'),
        pytest.param(
            YEARLY_INVOICE_ANALYTICS_INPUTS[5],
            id='yearly-uk-total-already-current-year',
        ),
        pytest.param(YEARLY_INVOICE_ANALYTICS_INPUTS[6], id='yearly-ru-total-current-year'),
        pytest.param(YEARLY_INVOICE_ANALYTICS_INPUTS[7], id='yearly-be-total-current-year'),
        pytest.param(GENERAL_INVOICE_ANALYTICS_INPUTS[0], id='general-uk-show-month'),
        pytest.param(GENERAL_INVOICE_ANALYTICS_INPUTS[1], id='general-uk-total-two-months'),
        pytest.param(GENERAL_INVOICE_ANALYTICS_INPUTS[2], id='general-sk-count-two-months'),
        pytest.param(GENERAL_INVOICE_ANALYTICS_INPUTS[3], id='general-sk-compare-two-months'),
        pytest.param(GENERAL_INVOICE_ANALYTICS_INPUTS[4], id='general-uk-total-by-month'),
        pytest.param(
            GENERAL_INVOICE_ANALYTICS_INPUTS[5],
            id='general-uk-compare-same-month-two-years',
        ),
        pytest.param(GENERAL_INVOICE_ANALYTICS_INPUTS[6], id='general-sk-unpaid-count'),
        pytest.param(
            GENERAL_INVOICE_ANALYTICS_INPUTS[7],
            id='general-sk-top-customers-by-total',
        ),
    ],
)
def test_invoice_analytics_resolves_as_read_only_top_level_action(user_input: str) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'invoice_analytics', 'unknown'],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'invoice_analytics'


def test_process_invoice_text_runs_invoice_analytics_without_side_effects(tmp_path: Path, monkeypatch) -> None:
    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    ContactService(config.db_path).create_contact(
        ContactProfile(
            supplier_telegram_id=111,
            name='Beta s.r.o.',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Hlavna 1, Kosice',
            email='',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    contact = ContactService(config.db_path).get_by_name(111, 'Beta s.r.o.')
    assert contact is not None and contact.id is not None
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=contact.id,
        invoice_number='20260001',
        issue_date='2026-05-10',
        delivery_date='2026-05-10',
        due_date='2026-05-24',
        due_days=14,
        total_amount=300,
        currency='EUR',
        status='unpaid',
        items=[
            CreateInvoiceItemPayload(
                description_raw='oprava',
                description_normalized='Oprava',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=300,
                total_price=300,
            )
        ],
    )
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=222,
        contact_id=999,
        invoice_number='20260099',
        issue_date='2026-05-10',
        delivery_date='2026-05-10',
        due_date='2026-05-24',
        due_days=14,
        total_amount=999,
        currency='EUR',
        status='unpaid',
        items=[
            CreateInvoiceItemPayload(
                description_raw='oprava',
                description_normalized='Oprava',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=999,
                total_price=999,
            )
        ],
    )

    async def _extractor(**kwargs) -> None:
        return None

    async def _resolver(**kwargs) -> str:
        if kwargs['context_name'] == 'top_level_action':
            return 'invoice_analytics'
        return 'unknown'

    async def _planner(**kwargs) -> InvoiceAnalyticsPlan:
        assert kwargs['current_date_iso']
        assert 'invoices_df' in kwargs['data_catalog']['datasets']
        assert kwargs['data_catalog']['customer_scope'] is None
        catalog_columns = kwargs['data_catalog']['datasets']['invoices_df']['columns']
        assert 'payment_status_canonical' in catalog_columns
        assert 'status' not in catalog_columns
        return InvoiceAnalyticsPlan(
            analysis_code=(
                'df = invoices_df.copy()\n'
                'result = {"summary": {"invoice_count": int(len(df)), "total": float(df["total_amount"].sum())}, "tables": {}, "warnings": [], "answer_hints": []}'
            ),
            answer_language='uk',
            reasoning_summary='count current supplier invoices',
        )

    async def _answer(**kwargs) -> str:
        assert kwargs['computed_result']['summary']['invoice_count'] == 1
        assert kwargs['computed_result']['summary']['total'] == 300.0
        assert 'supplier_telegram_id' not in kwargs['dataset_metadata']
        assert kwargs['answer_language'] == 'sk'
        return 'Máte 1 faktúru v sume 300.00 EUR.'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr(
        'bot.handlers.invoice.extract_invoice_analytics_customer_reference',
        _extractor,
    )
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _planner)
    monkeypatch.setattr('bot.handlers.invoice.answer_invoice_analytics', _answer)

    message = _authorized_message('Покажи фактури за травень', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.cleared is True
    assert message.answers[-1] == 'Máte 1 faktúru v sume 300.00 EUR.'
    assert message.documents == []
    assert not (tmp_path / 'invoices').exists()


def test_invoice_analytics_reuses_confirmed_contact_alias_before_bounded_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    contacts = ContactService(config.db_path)
    for name, ico in [('Tech Company s.r.o.', '12345678'), ('Other Company s.r.o.', '87654321')]:
        contacts.create_contact(
            ContactProfile(
                supplier_telegram_id=111,
                name=name,
                ico=ico,
                dic=f'{ico}00',
                ic_dph=None,
                address='Hlavna 1, Kosice',
                email='',
                contact_person=None,
                source_type='manual',
                source_note=None,
                contract_path=None,
            )
        )
    target = contacts.get_by_name(111, 'Tech Company s.r.o.')
    other = contacts.get_by_name(111, 'Other Company s.r.o.')
    assert target is not None and target.id is not None
    assert other is not None and other.id is not None

    contacts.create_confirmed_contact_alias(
        supplier_telegram_id=111,
        alias_text='\u0422\u0435\u0445 \u041a\u043e\u043c\u043f\u0430\u043d\u0456',
        contact_id=target.id,
        source='preview_approved',
    )

    invoices = InvoiceService(config.db_path)
    for contact_id, number, total in [
        (target.id, '20260001', 300),
        (other.id, '20260002', 900),
    ]:
        invoices.create_invoice_with_items(
            supplier_telegram_id=111,
            contact_id=contact_id,
            invoice_number=number,
            issue_date='2026-05-10',
            delivery_date='2026-05-10',
            due_date='2026-05-24',
            due_days=14,
            total_amount=total,
            currency='EUR',
            status='unpaid',
            items=[
                CreateInvoiceItemPayload(
                    description_raw='oprava',
                    description_normalized='Oprava',
                    item_description_raw=None,
                    quantity=1,
                    unit='ks',
                    unit_price=total,
                    total_price=total,
                )
            ],
        )

    async def _extractor(**kwargs) -> str:
        assert kwargs['user_question'].endswith('\u0422\u0435\u0445 \u041a\u043e\u043c\u043f\u0430\u043d\u0456.')
        return '\u0422\u0435\u0445 \u041a\u043e\u043c\u043f\u0430\u043d\u0456'

    async def _resolver(**kwargs) -> str:
        if kwargs['context_name'] == 'top_level_action':
            return 'invoice_analytics'
        raise AssertionError(
            'bounded contact fallback must not run after a confirmed alias match'
        )

    async def _planner(**kwargs) -> InvoiceAnalyticsPlan:
        assert kwargs['data_catalog']['customer_scope'] == {
            'canonical_name': 'Tech Company s.r.o.',
            'prefiltered_by_trusted_contact_id': True,
        }
        return InvoiceAnalyticsPlan(
            analysis_code=(
                'df = invoices_df.copy()\n'
                'result = {"summary": {"invoice_count": int(len(df)), "total": float(df["total_amount"].sum())}, "tables": {}, "warnings": [], "answer_hints": []}'
            ),
            answer_language='uk',
            reasoning_summary='sum prefiltered customer invoices',
        )

    async def _answer(**kwargs) -> str:
        assert kwargs['computed_result']['summary'] == {
            'invoice_count': 1,
            'total': 300.0,
        }
        assert kwargs['dataset_metadata']['customer_scope'] == 'Tech Company s.r.o.'
        return 'Pre Tech Company je suma 300.00 EUR.'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr(
        'bot.handlers.invoice.extract_invoice_analytics_customer_reference',
        _extractor,
        raising=False,
    )
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _planner)
    monkeypatch.setattr('bot.handlers.invoice.answer_invoice_analytics', _answer)

    message = _authorized_message(
        '\u041f\u043e\u043a\u0430\u0436\u0438 \u0441\u0443\u043c\u0443 \u0432\u0438\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u0438\u0445 \u0444\u0430\u043a\u0442\u0443\u0440 \u0434\u043b\u044f \u0422\u0435\u0445 \u041a\u043e\u043c\u043f\u0430\u043d\u0456.',
        telegram_id=111,
    )
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text=message.text,
        )
    )

    assert state.cleared is True
    assert message.answers[-1] == 'Pre Tech Company je suma 300.00 EUR.'
    assert message.documents == []
    assert not (tmp_path / 'invoices').exists()


def test_invoice_analytics_validation_stop_logs_reason(tmp_path: Path, monkeypatch, caplog) -> None:
    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        invoice_number='20260001',
        issue_date='2026-05-10',
        delivery_date='2026-05-10',
        due_date='2026-05-24',
        due_days=14,
        total_amount=300,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='oprava',
                description_normalized='Oprava',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=300,
                total_price=300,
            )
        ],
    )

    async def _resolver(**kwargs) -> str:
        return 'invoice_analytics' if kwargs['context_name'] == 'top_level_action' else 'unknown'

    async def _planner(**kwargs) -> InvoiceAnalyticsPlan:
        return InvoiceAnalyticsPlan(
            analysis_code='df = invoices_df.copy()\nresult = {}',
            answer_language='sk',
            reasoning_summary='validation failure test',
        )

    def _execute(**kwargs):
        raise AnalyticsCodeValidationError('name_not_allowed:datetime')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _planner)
    monkeypatch.setattr('bot.handlers.invoice.execute_invoice_analytics_code', _execute)

    message = _authorized_message('Покажи фактури за травень', telegram_id=111)
    state = _DummyState()

    with caplog.at_level('WARNING', logger='bot.handlers.invoice'):
        asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert 'Analytický výpočet som zastavil' in message.answers[-1]
    assert any(
        'Invoice analytics execution stopped' in record.message
        and 'AnalyticsCodeValidationError' in record.message
        and 'name_not_allowed:datetime' in record.message
        and 'row_count=1' in record.message
        for record in caplog.records
    )


def test_invoice_analytics_repairs_invalid_generated_code_before_user_fallback(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        invoice_number='20260001',
        issue_date='2026-05-10',
        delivery_date='2026-05-10',
        due_date='2026-05-24',
        due_days=14,
        total_amount=300,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='oprava',
                description_normalized='Oprava',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=300,
                total_price=300,
            )
        ],
    )
    planner_calls: list[dict] = []

    async def _resolver(**kwargs) -> str:
        return 'invoice_analytics' if kwargs['context_name'] == 'top_level_action' else 'unknown'

    async def _planner(**kwargs) -> InvoiceAnalyticsPlan:
        planner_calls.append(kwargs)
        if len(planner_calls) == 1:
            assert kwargs['repair_feedback'] is None
            return InvoiceAnalyticsPlan(
                analysis_code='df = invoices_df.copy()\nvalue = datetime.now()\nresult = {}',
                answer_language='uk',
                reasoning_summary='invalid first plan',
            )
        assert kwargs['repair_feedback']['stage'] == 'execution'
        assert kwargs['repair_feedback']['error_type'] == 'AnalyticsCodeValidationError'
        assert kwargs['repair_feedback']['error_reason'] == 'name_not_allowed:datetime'
        assert 'datetime.now()' in kwargs['repair_feedback']['previous_analysis_code']
        return InvoiceAnalyticsPlan(
            analysis_code=(
                'df = invoices_df.copy()\n'
                'result = {"summary": {"invoice_count": int(len(df)), "total": float(df["total_amount"].sum())}, "tables": {}, "warnings": [], "answer_hints": []}'
            ),
            answer_language='uk',
            reasoning_summary='opraveny plan: suma ulozenych vystavenych faktur',
        )

    def _execute(**kwargs):
        if 'datetime.now()' in kwargs['code']:
            raise AnalyticsCodeValidationError('name_not_allowed:datetime')
        return SimpleNamespace(
            result={'summary': {'invoice_count': 1, 'total': 300.0}, 'tables': {}, 'warnings': [], 'answer_hints': []},
            warnings=(),
        )

    async def _answer(**kwargs) -> str:
        assert kwargs['computed_result']['summary'] == {'invoice_count': 1, 'total': 300.0}
        assert kwargs['answer_language'] == 'sk'
        return 'Máte 1 faktúru v sume 300.00 EUR.'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _planner)
    monkeypatch.setattr('bot.handlers.invoice.execute_invoice_analytics_code', _execute)
    monkeypatch.setattr('bot.handlers.invoice.answer_invoice_analytics', _answer)

    message = _authorized_message('Покажи фактури за травень', telegram_id=111)
    state = _DummyState()

    with caplog.at_level('WARNING', logger='bot.handlers.invoice'):
        asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert len(planner_calls) == 2
    assert message.answers[-1] == 'Máte 1 faktúru v sume 300.00 EUR.'
    assert 'Analytický výpočet som zastavil' not in message.answers[-1]
    assert state.cleared is True
    assert any('attempt=1' in record.message and 'name_not_allowed:datetime' in record.message for record in caplog.records)


def test_process_invoice_text_invoice_analytics_missing_db_returns_empty_answer(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'invoice_analytics' if kwargs['context_name'] == 'top_level_action' else 'unknown'

    async def _unexpected_planner(**kwargs) -> InvoiceAnalyticsPlan:
        raise AssertionError('planner must not run for empty missing DB dataset')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _unexpected_planner)

    message = _authorized_message('Покажи фактури за травень', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text=message.text))

    assert 'nenašiel žiadne uložené vystavené faktúry' in message.answers[-1]
    assert state.cleared is True
    assert not (tmp_path / 'test.db').exists()
    assert 'Nerozumiem, čo chcete spraviť.' not in message.answers[-1]
    assert 'read-only odoslané faktúry' in message.answers[-1]


@pytest.mark.parametrize(
    'user_input',
    [
        'Ти можеш порахувати видатки згідно чеків по місяцям?',
        'Покажи витрати по чеках за місяцями.',
        'покажи видатки за цей рік',
        'Vieš analyzovať výdavky podľa bločkov?',
        'Can you analyze my receipts by month?',
    ],
)
def test_process_invoice_text_routes_supported_expense_domains_to_accounting_document_analytics_empty_answer(
    tmp_path: Path,
    monkeypatch,
    user_input: str,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'invoice_analytics' if kwargs['context_name'] == 'top_level_action' else 'unknown'

    async def _unexpected_planner(**kwargs) -> InvoiceAnalyticsPlan:
        raise AssertionError('invoice planner must not run for receipt or expense analytics requests')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _unexpected_planner)

    message = _authorized_message(user_input, telegram_id=111)
    state = _DummyState()
    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    answer = message.answers[-1]
    assert 'nenašiel žiadne potvrdené bločky ani prijaté faktúry' in answer
    assert 'read-only potvrdené účtovné doklady' in answer
    assert state.cleared is True
    assert message.documents == []
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []

def test_unsupported_tax_analytics_preview_approval_saves_one_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'invoice_analytics' if kwargs['context_name'] == 'top_level_action' else 'unknown'

    async def _unexpected_planner(**kwargs) -> InvoiceAnalyticsPlan:
        raise AssertionError('planner must not run for unsupported tax analytics requests')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _unexpected_planner)

    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('Vieš spraviť DPH report z bločkov?', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == CustomizationRequestStates.waiting_preview_decision
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []

    asyncio.run(
        customization_request_preview_decision(
            message=_authorized_message('schváliť', telegram_id=111),
            state=state,
            config=config,
        )
    )

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1
    assert records[0].source_triage_class == 'new_business_feature_request'
    assert records[0].source_capability_id == 'bank_cashflow_tax_analytics'
    assert records[0].source_topic_id == 'bank_cashflow_tax_analytics'
    assert records[0].status == 'confirmed_pending_review'


def test_known_reserved_send_invoice_action_uses_product_truth_and_does_not_execute(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('pošli faktúru 20260001')
    state = _DummyState()
    async def _resolver(**kwargs):
        return 'send_invoice'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='pošli faktúru 20260001',
        )
    )

    assert state.cleared is True
    assert 'Odosielanie faktúr emailom' in message.answers[-1]
    assert 'nepodporovan' in message.answers[-1]
    assert 'Email delivery is configured.' not in message.answers[-1]


@pytest.mark.parametrize(
    ('user_input', 'expected_fragment'),
    [
        ('Ak\u00e9 bude po\u010dasie zajtra?', 'mimo rozsahu OfficeFlow'),
        ('@@@ #### !!!', 'Tomuto vstupu nerozumiem'),
        ('Ako sa m\u00e1\u0161?', 'biznis \u00falohami'),
        ('urob mi to', 'Nie je jasn\u00e9'),
    ],
)
def test_process_invoice_text_uses_bounded_info_help_triage_without_side_effects(
    tmp_path: Path,
    user_input: str,
    expected_fragment: str,
) -> None:
    message = _DummyMessage(user_input)
    state = _DummyState()
    config = _config(tmp_path)

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=user_input))

    assert state.cleared is True
    assert state.current_state is None
    assert expected_fragment in message.answers[-1]
    assert 'podporovan\u00e9' not in message.answers[-1]
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_eligible_triage_creates_customization_preview_only_no_db_row(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('Vie\u0161 mi spravi\u0165 preh\u013ead tr\u017eieb za minul\u00fd mesiac?')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == CustomizationRequestStates.waiting_preview_decision
    assert 'N\u00e1vrh po\u017eiadavky' in message.answers[-1]
    assert 'Nestane sa: ni\u010d neimplementujem, ni\u010d neposielam spr\u00e1vcovi, nemen\u00edm Product Truth.' in message.answers[-1]
    draft = state.data['customization_request_draft']
    assert draft['requester_telegram_id'] == 111
    assert str(draft['request_id']).startswith('cr_')
    assert draft['redacted_original_text'] == message.text
    assert isinstance(draft['raw_text_hash'], str)
    assert 'original_user_text' not in draft
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []


@pytest.mark.parametrize(
    'triage_class',
    [
        'new_business_feature_request',
        'customization_request_candidate',
        'admin_review_candidate',
        'possible_product_truth_candidate',
    ],
)
def test_all_eligible_triage_classes_create_preview_only(
    tmp_path: Path,
    monkeypatch,
    triage_class: str,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'unknown'

    async def _triage(**kwargs) -> InfoHelpTriageResult:
        return InfoHelpTriageResult(
            capability_id='unknown',
            topic_id='new_business_feature',
            triage_class=triage_class,
            confidence=0.7,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_triage_result_with_llm', _triage)
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('Potrebujem nov\u00fd firemn\u00fd workflow.')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == CustomizationRequestStates.waiting_preview_decision
    assert state.data['customization_request_draft']['source_triage_class'] == triage_class
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []


def test_invoice_period_summary_resolver_fallback_is_product_truth_not_customization_preview(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'unknown'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('Na ak\u00fa sumu som vystavil fakt\u00fary v tomto roku?')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.cleared is True
    assert state.current_state is None
    assert 'Analytika vystaven\u00fdch fakt\u00far' in message.answers[-1]
    assert '\u010diasto\u010dn' in message.answers[-1]
    assert 'read-only pilot' in message.answers[-1]
    assert 'N\u00e1vrh po\u017eiadavky' not in message.answers[-1]
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []


def test_customization_request_approve_saves_one_confirmed_pending_review_row(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('Vie\u0161 mi spravi\u0165 preh\u013ead tr\u017eieb za minul\u00fd mesiac?')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    draft_request_id = state.data['customization_request_draft']['request_id']
    approve_message = _authorized_message('schv\u00e1li\u0165')
    asyncio.run(
        customization_request_preview_decision(
            message=approve_message,
            state=state,
            config=config,
        )
    )

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1
    assert records[0].status == 'confirmed_pending_review'
    assert records[0].request_id == draft_request_id
    assert records[0].source_triage_class == 'new_business_feature_request'
    assert records[0].telegram_id == 111
    assert records[0].supplier_telegram_id == 111
    assert approve_message.answers[-1] == (
        'Po\u017eiadavku som ulo\u017eil na neskor\u0161iu kontrolu. '
        'Neznamen\u00e1 to, \u017ee funkcia je podporovan\u00e1 alebo \u017ee bude implementovan\u00e1.'
    )


def test_customization_request_cancel_saves_nothing(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Povedz adminovi, \u017ee potrebujem automatick\u00e9 pripomienky fakt\u00far.')

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    cancel_message = _authorized_message('zru\u0161i\u0165')
    asyncio.run(
        customization_request_preview_decision(
            message=cancel_message,
            state=state,
            config=config,
        )
    )

    assert 'Zru\u0161en\u00e9. Po\u017eiadavku som neulo\u017eil.' in cancel_message.answers[-1]
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []


def test_customization_request_edit_then_approve_saves_edited_title_summary(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.')

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    asyncio.run(customization_request_preview_decision(message=_authorized_message('upravi\u0165'), state=state, config=config))
    edit_message = _authorized_message('Mesa\u010dn\u00fd report tr\u017eieb\nChcem s\u00fa\u010det tr\u017eieb po mesiacoch.')
    asyncio.run(customization_request_edit_text(message=edit_message, state=state))
    asyncio.run(customization_request_preview_decision(message=_authorized_message('schv\u00e1li\u0165'), state=state, config=config))

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1
    assert records[0].normalized_title == 'Mesa\u010dn\u00fd report tr\u017eieb'
    assert records[0].normalized_summary == 'Chcem s\u00fa\u010det tr\u017eieb po mesiacoch.'


def test_customization_request_edit_preserves_draft_identity(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb pre test@example.com.')

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    original_draft = dict(state.data['customization_request_draft'])
    asyncio.run(customization_request_preview_decision(message=_authorized_message('upravi\u0165'), state=state, config=config))
    edit_message = _authorized_message('Mesa\u010dn\u00fd report\nZhrnutie po \u00faprave.')
    asyncio.run(customization_request_edit_text(message=edit_message, state=state))

    edited_draft = state.data['customization_request_draft']
    assert edited_draft['normalized_title'] == 'Mesa\u010dn\u00fd report'
    assert edited_draft['normalized_summary'] == 'Zhrnutie po \u00faprave.'
    assert edited_draft['request_id'] == original_draft['request_id']
    assert edited_draft['requester_telegram_id'] == original_draft['requester_telegram_id']
    assert edited_draft['supplier_telegram_id'] == original_draft['supplier_telegram_id']
    assert edited_draft['workspace_id'] == original_draft['workspace_id']
    assert edited_draft['redacted_original_text'] == original_draft['redacted_original_text']
    assert edited_draft['raw_text_hash'] == original_draft['raw_text_hash']


def test_customization_request_double_approve_does_not_create_duplicate(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.')

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    asyncio.run(customization_request_preview_decision(message=_authorized_message('schv\u00e1li\u0165'), state=state, config=config))
    asyncio.run(customization_request_preview_decision(message=_authorized_message('schv\u00e1li\u0165'), state=state, config=config))

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1


def test_customization_request_same_draft_duplicate_approve_is_idempotent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    initial_state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.')

    asyncio.run(process_invoice_text(message=message, state=initial_state, config=config, invoice_text=message.text))
    draft = dict(initial_state.data['customization_request_draft'])
    first_state = _DummyState()
    first_state.data = {
        'customization_request_draft': dict(draft),
        'customization_request_saved_id': None,
    }
    second_state = _DummyState()
    second_state.data = {
        'customization_request_draft': dict(draft),
        'customization_request_saved_id': None,
    }

    asyncio.run(customization_request_preview_decision(message=_authorized_message('schv\u00e1li\u0165'), state=first_state, config=config))
    duplicate_message = _authorized_message('schv\u00e1li\u0165')
    asyncio.run(customization_request_preview_decision(message=duplicate_message, state=second_state, config=config))

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1
    assert records[0].request_id == draft['request_id']
    assert '\u010fal\u0161iu k\u00f3piu' in duplicate_message.answers[-1]


def test_customization_request_approval_rejects_non_owner(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.', telegram_id=111)

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    approve_message = _authorized_message('schv\u00e1li\u0165', telegram_id=222)
    asyncio.run(customization_request_preview_decision(message=approve_message, state=state, config=config))

    service = CustomizationRequestService(config.db_path)
    assert service.list_customization_requests_for_user(telegram_id=111) == []
    assert service.list_customization_requests_for_user(telegram_id=222) == []
    assert 'in\u00e9mu pou\u017e\u00edvate\u013eovi' in approve_message.answers[-1]


def test_customization_request_duplicate_request_id_is_idempotent(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.')

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    draft = state.data['customization_request_draft']
    service = CustomizationRequestService(config.db_path)
    service.create_confirmed_customization_request(
        request_id=str(draft['request_id']),
        telegram_id=111,
        supplier_telegram_id=111,
        workspace_id='telegram:111',
        source_channel='text',
        source_triage_class=str(draft['source_triage_class']),
        normalized_title='Existing request',
        normalized_summary='Already saved request',
        redacted_original_text=str(draft['redacted_original_text']),
        raw_text_hash=str(draft['raw_text_hash']),
    )

    approve_message = _authorized_message('schv\u00e1li\u0165')
    asyncio.run(customization_request_preview_decision(message=approve_message, state=state, config=config))

    records = service.list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1
    assert records[0].request_id == draft['request_id']
    assert '\u010fal\u0161iu k\u00f3piu' in approve_message.answers[-1]


def test_customization_request_cross_user_duplicate_request_id_fails_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.', telegram_id=111)

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    draft = state.data['customization_request_draft']
    service = CustomizationRequestService(config.db_path)
    service.create_confirmed_customization_request(
        request_id=str(draft['request_id']),
        telegram_id=222,
        supplier_telegram_id=222,
        workspace_id='telegram:222',
        source_channel='text',
        source_triage_class=str(draft['source_triage_class']),
        normalized_title='Other user request',
        normalized_summary='Belongs to another tenant.',
        redacted_original_text='Belongs to another tenant.',
        raw_text_hash='2' * 64,
    )

    approve_message = _authorized_message('schv\u00e1li\u0165', telegram_id=111)
    asyncio.run(customization_request_preview_decision(message=approve_message, state=state, config=config))

    assert service.list_customization_requests_for_user(telegram_id=111) == []
    other_records = service.list_customization_requests_for_user(telegram_id=222)
    assert len(other_records) == 1
    assert other_records[0].request_id == draft['request_id']
    assert 'Other user request' not in approve_message.answers[-1]
    assert 'Belongs to another tenant' not in approve_message.answers[-1]
    assert 'Nevytvoril som \u010fal\u0161iu k\u00f3piu' in approve_message.answers[-1]


def test_customization_request_duplicate_non_pending_request_id_fails_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.')

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    draft = state.data['customization_request_draft']
    service = CustomizationRequestService(config.db_path)
    service.create_confirmed_customization_request(
        request_id=str(draft['request_id']),
        telegram_id=111,
        supplier_telegram_id=111,
        workspace_id='telegram:111',
        source_channel='text',
        source_triage_class=str(draft['source_triage_class']),
        normalized_title='Reviewed request',
        normalized_summary='This request is already reviewed.',
        redacted_original_text=str(draft['redacted_original_text']),
        raw_text_hash=str(draft['raw_text_hash']),
        status='reviewed_rejected',
    )

    approve_message = _authorized_message('schv\u00e1li\u0165')
    asyncio.run(customization_request_preview_decision(message=approve_message, state=state, config=config))

    records = service.list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1
    assert records[0].request_id == draft['request_id']
    assert records[0].status == 'reviewed_rejected'
    assert 'Nevytvoril som \u010fal\u0161iu k\u00f3piu' in approve_message.answers[-1]


def test_unauthorized_user_cannot_start_or_save_customization_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('Treba mesa\u010dn\u00fd report tr\u017eieb.')
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.cleared is True
    assert state.current_state is None
    assert 'Po\u017eiadavku som neulo\u017eil' in message.answers[-1]
    assert CustomizationRequestService(config.db_path).list_pending_customization_requests_for_admin() == []


def test_customization_request_saved_row_is_tenant_scoped_and_redacted(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message(
        'Chcem vlastn\u00fa \u00fapravu fakt\u00fary pre test@example.com token sk-1234567890abcdef',
        telegram_id=222,
    )

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    asyncio.run(
        customization_request_preview_decision(
            message=_authorized_message('schv\u00e1li\u0165', telegram_id=222),
            state=state,
            config=config,
        )
    )

    service = CustomizationRequestService(config.db_path)
    assert service.list_customization_requests_for_user(telegram_id=111) == []
    records = service.list_customization_requests_for_user(telegram_id=222)
    assert len(records) == 1
    assert records[0].telegram_id == 222
    assert records[0].supplier_telegram_id == 222
    assert '[REDACTED]' in records[0].normalized_summary
    assert 'test@example.com' not in records[0].normalized_title
    assert 'test@example.com' not in records[0].normalized_summary
    assert 'sk-1234567890abcdef' not in records[0].normalized_title
    assert 'sk-1234567890abcdef' not in records[0].normalized_summary
    assert records[0].redacted_original_text is not None
    assert 'test@example.com' not in records[0].redacted_original_text
    assert 'sk-1234567890abcdef' not in records[0].redacted_original_text


def test_customization_request_flow_does_not_mutate_product_truth_or_create_handoff(tmp_path: Path) -> None:
    before = [(cap.capability_id, cap.status.value, cap.summary_for_user) for cap in list_capabilities()]
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _authorized_message('Treba mesa\u010dn\u00fd report tr\u017eieb.')

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))
    asyncio.run(customization_request_preview_decision(message=_authorized_message('schv\u00e1li\u0165'), state=state, config=config))

    after = [(cap.capability_id, cap.status.value, cap.summary_for_user) for cap in list_capabilities()]
    service = CustomizationRequestService(config.db_path)
    assert after == before
    assert not hasattr(service, 'notify_admin')
    assert not hasattr(service, 'send_admin_notification')
    assert not hasattr(service, 'create_code_agent_handoff')


@pytest.mark.parametrize(
    'user_input',
    [
        'Ak\u00e9 bude po\u010dasie zajtra?',
        '@@@ #### !!!',
        'Ako sa m\u00e1\u0161?',
        'urob mi to',
        'cashflow maybe maybe',
    ],
)
def test_noneligible_triage_does_not_start_customization_draft(tmp_path: Path, user_input: str) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _authorized_message(user_input)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=user_input))

    assert state.current_state is None
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []


def test_process_invoice_text_unknown_can_use_llm_info_help_triage_without_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'unknown'

    _InfoHelpTriageOpenAIFake.output = json.dumps(
        {
            'capability_id': 'unknown',
            'topic_id': 'new_business_feature',
            'triage_class': 'new_business_feature_request',
            'confidence': 0.82,
            'needs_clarification': False,
            'request_draft': {'title': 'Do not persist'},
            'admin_message': 'Do not send',
        }
    )
    _InfoHelpTriageOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpTriageOpenAIFake)

    config = Config(
        bot_token='token',
        openai_api_key='sk-test',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )
    message = _authorized_message('custom widget pls')
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text='custom widget pls',
        )
    )

    assert state.current_state == CustomizationRequestStates.waiting_preview_decision
    assert 'N\u00e1vrh po\u017eiadavky' in message.answers[-1]
    assert 'Nestane sa: ni\u010d neimplementujem' in message.answers[-1]
    assert _InfoHelpTriageOpenAIFake.last_payload is not None
    assert _InfoHelpTriageOpenAIFake.last_payload['input_channel'] == 'text'
    assert 'request_draft' not in _InfoHelpTriageOpenAIFake.last_payload
    assert 'admin_message' not in _InfoHelpTriageOpenAIFake.last_payload
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_process_invoice_text_llm_unknown_falls_back_to_generic_guidance_without_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'unknown'

    _InfoHelpTriageOpenAIFake.output = json.dumps(
        {
            'capability_id': 'unknown',
            'topic_id': 'unknown',
            'triage_class': 'unknown',
            'confidence': 0.0,
            'needs_clarification': False,
        }
    )
    _InfoHelpTriageOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpTriageOpenAIFake)

    config = Config(
        bot_token='token',
        openai_api_key='sk-test',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage('lorem ipsum maybe')
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text='lorem ipsum maybe',
        )
    )

    assert state.cleared is True
    assert 'Nerozumiem, \u010do chcete spravi\u0165.' in message.answers[-1]
    assert 'vytvori\u0165 fakt\u00faru' in message.answers[-1]
    assert _InfoHelpTriageOpenAIFake.last_payload is not None
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_process_invoice_text_llm_possible_product_truth_candidate_asks_clarification_without_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'unknown'

    _InfoHelpTriageOpenAIFake.output = json.dumps(
        {
            'capability_id': 'unknown',
            'topic_id': 'possible_product_truth_candidate',
            'triage_class': 'possible_product_truth_candidate',
            'confidence': 0.62,
            'needs_clarification': False,
            'primary_status': 'supported',
        }
    )
    _InfoHelpTriageOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpTriageOpenAIFake)

    config = Config(
        bot_token='token',
        openai_api_key='sk-test',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )
    message = _authorized_message('viete spravit veci okolo workflow?')
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text='viete spravit veci okolo workflow?',
        )
    )

    assert state.current_state == CustomizationRequestStates.waiting_preview_decision
    assert 'N\u00e1vrh po\u017eiadavky' in message.answers[-1]
    assert 'supported' not in message.answers[-1]
    assert _InfoHelpTriageOpenAIFake.last_payload is not None
    assert 'primary_status' not in _InfoHelpTriageOpenAIFake.last_payload
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_email_capability_question_uses_product_truth_not_invoice_execution(tmp_path: Path) -> None:
    message = _DummyMessage('Vieš poslať faktúru emailom?')
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='Vieš poslať faktúru emailom?',
        )
    )

    assert state.cleared is True
    assert 'Odosielanie faktúr emailom' in message.answers[-1]
    assert 'nepodporovan' in message.answers[-1]
    assert 'Bot nie je nakonfigurovan' not in message.answers[-1]


def test_delete_database_question_uses_safety_guidance_not_delete_flow(tmp_path: Path) -> None:
    message = _DummyMessage('Ako môžem vymazať databázu?')
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='Ako môžem vymazať databázu?',
        )
    )

    assert state.cleared is True
    assert state.current_state is None
    assert 'Vymazanie používateľskej databázy' in message.answers[-1]
    assert 'citliv' in message.answers[-1]


@pytest.mark.parametrize(
    ('user_input', 'expected_title', 'expected_status_fragment'),
    [
        ('Vieš exportovať podklady pre účtovníctvo?', 'Export do účtovníctva', 'nepodporovan'),
        ('Môžem si upraviť PDF šablónu?', 'Vlastná PDF šablóna faktúry', 'nepodporovan'),
        ('Chcem vlastnú funkciu', 'Požiadavky na úpravu', 'čiastoč'),
        ('Vieš odovzdať úlohu code agentovi?', 'Odovzdanie úlohy kódovaciemu agentovi', 'nepodporovan'),
        ('Ako vymažem databázu?', 'Vymazanie používateľskej databázy', 'citliv'),
    ],
)
def test_product_ux_info_help_smoke_phrases_do_not_execute_actions(
    tmp_path: Path,
    monkeypatch,
    user_input: str,
    expected_title: str,
    expected_status_fragment: str,
) -> None:
    unexpected_calls: list[str] = []

    async def _unexpected_start_edit(**kwargs):
        unexpected_calls.append('edit_existing_invoice')

    async def _unexpected_delete_database(**kwargs):
        unexpected_calls.append('delete_user_database')

    monkeypatch.setattr('bot.handlers.invoice.start_invoice_edit_flow', _unexpected_start_edit)
    monkeypatch.setattr('bot.handlers.invoice.start_delete_user_database_flow', _unexpected_delete_database)

    message = _DummyMessage(user_input)
    state = _DummyState()
    config = _config(tmp_path)

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=user_input))

    assert unexpected_calls == []
    assert state.cleared is True
    assert state.current_state is None
    assert expected_title in message.answers[-1]
    assert expected_status_fragment in message.answers[-1]
    assert 'Bot nie je nakonfigurovan' not in message.answers[-1]
    assert not config.db_path.exists()


def test_direct_invoice_creation_text_still_routes_to_invoice_flow(tmp_path: Path) -> None:
    message = _DummyMessage('Vytvor faktúru pre ABC za opravu 100 eur')
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='Vytvor faktúru pre ABC za opravu 100 eur',
        )
    )

    assert state.cleared is True
    assert 'Bot nie je nakonfigurovan' in message.answers[-1]
    assert 'Product Truth' not in message.answers[-1]


def test_active_fsm_top_level_text_does_not_route_to_info_help(tmp_path: Path, monkeypatch) -> None:
    calls: list[str | None] = []

    def _info_help(**kwargs) -> str:
        calls.append(kwargs.get('user_input_text'))
        return 'unexpected'

    monkeypatch.setattr('bot.handlers.invoice.build_top_level_unknown_guidance', _info_help)
    state = _DummyState()
    state.current_state = InvoiceStates.waiting_edit_scope

    asyncio.run(semantic_top_level_input(_DummyMessage('blabla'), state, _config(tmp_path)))

    assert calls == []


def test_info_help_guidance_builder_has_no_side_effects() -> None:
    first = build_top_level_unknown_guidance(user_input_text='blabla')
    second = build_top_level_unknown_guidance(user_input_text='niečo iné')

    assert first == second
    assert 'Nerozumiem, čo chcete spraviť.' in first
    assert 'vytvoriť faktúru' in first
    assert 'spočítať súhrn vystavených faktúr za kalendárny rok' in first
    assert 'súhrn faktúr za 2026' in first


def test_process_invoice_text_keeps_partial_draft_when_only_service_slot_is_unknown(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        partial_payload = {
            'vstup': {'povodny_text': 'faktura pre Tech Company 150 EUR', 'zisteny_jazyk': 'sk'},
            'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.9},
            'biznis_sk': {
                'odberatel_kandidat': 'Tech Company',
                'polozka_povodna': 'оправы',
                'termin_sluzby_sk': 'неясно',
                'mnozstvo': 1,
                'jednotka': 'ks',
                'suma': 150,
                'cena_za_jednotku': 150,
                'mena': 'EUR',
                'datum_dodania': None,
                'splatnost_dni': 14,
                'datum_splatnosti': None,
            },
            'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
        }
        raise LlmInvoicePayloadError(
            'service unresolved',
            error_code='service_term_unresolved',
            partial_payload=partial_payload,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is False
    assert state.current_state == InvoiceStates.waiting_service_clarification
    assert 'invoice_partial_draft' in state.data
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť typ služby. Spresnite ho, prosím.'


def test_process_invoice_text_keeps_partial_draft_when_customer_slot_is_unknown(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        partial_payload = {
            'vstup': {'povodny_text': 'faktura za opravu 150 EUR', 'zisteny_jazyk': 'sk'},
            'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.9},
            'biznis_sk': {
                'odberatel_kandidat': 'pre firmu',
                'polozka_povodna': 'oprava',
                'termin_sluzby_sk': 'oprava',
                'mnozstvo': 1,
                'jednotka': 'ks',
                'suma': 150,
                'cena_za_jednotku': 150,
                'mena': 'EUR',
                'datum_dodania': '2026-04-12',
                'splatnost_dni': 14,
                'datum_splatnosti': None,
            },
            'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
        }
        raise LlmInvoicePayloadError(
            'customer unresolved',
            error_code='customer_unresolved',
            partial_payload=partial_payload,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is False
    assert state.current_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'customer_name'
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť odberateľa. Spresnite názov firmy, prosím.'


def test_service_clarification_continues_to_preview_without_restart(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('oprava')
    message.from_user = type('User', (), {'id': 777})()
    state = _DummyState()
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    SupplierService(db_path).create_or_replace(
        SupplierProfile(
            telegram_id=777,
            name='Dodavatel SK',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Bratislava 1',
            iban='SK3112000000198742637541',
            swift='TATRSKBX',
            email='supplier@example.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    supplier = SupplierService(db_path).get_by_telegram_id(777)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(
        int(supplier.id),
        service_short_name='oprava',
        service_display_name='Servis a oprava zariadenia',
    )
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-1',
        'raw_text': 'faktura pre Tech Company 150 EUR',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'оправы',
            'service_term_sk': 'неясно',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': None,
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_service_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='oprava',
        )
    )

    assert captured['parsed_draft']['service_term_sk'] == 'oprava'
    assert captured['parsed_draft']['item_name_raw'] == 'oprava'
    assert captured['raw_text'] == 'faktura pre Tech Company 150 EUR'


def test_slot_clarification_applies_delivery_date_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('13.04.2026')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-2',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'delivery_date',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': None,
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='13.04.2026',
        )
    )

    assert captured['parsed_draft']['delivery_date'] == '2026-04-13'


def test_slot_clarification_applies_due_days_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('21')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-3',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'due_days',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': None,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='21',
        )
    )

    assert captured['parsed_draft']['due_days'] == 21


def test_slot_clarification_applies_unit_price_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('250')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-4',
        'raw_text': 'faktura pre Tech Company oprava 2x',
        'unresolved_slot': 'unit_price',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 2,
            'unit': 'ks',
            'amount': None,
            'unit_price': None,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='250',
        )
    )

    assert captured['parsed_draft']['unit_price'] == 250.0


def test_singleton_item_uses_top_level_quantity_and_price_from_llm_payload() -> None:
    parsed_draft = {
        'service_raw_mention': 'оправи',
        'item_name_raw': 'opravy',
        'service_term_sk': 'oprava',
        'quantity': 1.0,
        'unit': 'ks',
        'amount': None,
        'unit_price': 3490.0,
        'items': [
            {
                'item_name_raw': 'opravy',
                'service_raw_mention': 'оправи',
                'service_term_sk': 'oprava',
                'quantity': None,
                'unit': None,
                'amount': None,
                'unit_price': None,
                'item_description_raw': None,
            }
        ],
    }

    items = _normalize_items_input(parsed_draft)

    assert items == [
        {
            'item_name_raw': 'opravy',
            'service_raw_mention': 'оправи',
            'service_term_sk': 'oprava',
            'quantity': 1.0,
            'unit': 'ks',
            'amount': None,
            'unit_price': 3490.0,
            'item_description_raw': None,
        }
    ]


@pytest.mark.parametrize(
    'clarification_text,expected_quantity,expected_unit_price',
    [
        ('3 1500', 3.0, 1500.0),
        ('3 * 1500', 3.0, 1500.0),
        ('3 po 1500', 3.0, 1500.0),
        ('три kusy по 1500', 3.0, 1500.0),
        ('množstvo 3, cena za kus 1500', 3.0, 1500.0),
        ('количество 3, цена 1500', 3.0, 1500.0),
        ('2 крат по 1500', 2.0, 1500.0),
        ('два крат по 1500', 2.0, 1500.0),
        ('dva krát po 1500', 2.0, 1500.0),
        ('1500', 1.0, 1500.0),
        ('3000', 1.0, 3000.0),
    ],
)
def test_slot_clarification_applies_quantity_unit_price_pair_and_continues_to_preview(
    tmp_path: Path, monkeypatch, clarification_text: str, expected_quantity: float, expected_unit_price: float
) -> None:
    message = _DummyMessage(clarification_text)
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-qp',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'quantity_unit_price_pair',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': None,
            'unit': 'ks',
            'amount': None,
            'unit_price': None,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text=clarification_text,
        )
    )

    assert captured['parsed_draft']['quantity'] == expected_quantity
    assert captured['parsed_draft']['unit_price'] == expected_unit_price


def test_process_invoice_text_fails_loudly_on_fatal_payload_error(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        raise LlmInvoicePayloadError('fatal shape issue', error_code='fatal_payload')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is True
    assert message.answers[-1] == 'AI návrh faktúry bol neplatný. Skúste vstup poslať znova.'


def test_preview_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('maybe')
    state = _DummyState()
    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=_config(tmp_path),
            confirmation_text='maybe',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'


def test_postpdf_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('later')
    state = _DummyDecisionState()
    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=_config(tmp_path),
            decision_text='later',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'


@pytest.mark.parametrize(
    'user_input',
    [
        'Koľko som minul na palivo tento mesiac?',
        'Koľko bolo bločkov v kategórii materiál?',
        'Ukáž sumy podľa kategórií za jún',
        'Koľko som minul v BAUHAUS?',
        'Koľko mám prijatých faktúr za jún?',
    ],
)
def test_accounting_document_analytics_resolves_as_separate_read_only_top_level_action(user_input: str) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'invoice_analytics',
                'accounting_document_analytics',
                'add_receipt',
                'show_recent_accounting_documents',
                'unknown',
            ],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'accounting_document_analytics'


@pytest.mark.parametrize(
    'user_input',
    [
        'Vies spravit DPH report z blockov?',
        'Spocitaj danovo uznatelne vydavky z blockov.',
        'Porovnaj blocky s bankovymi pohybmi.',
        'Exportuj vydavky z blockov do uctovnictva.',
    ],
)
def test_unsupported_receipt_analytics_requests_route_to_guarded_python_path(user_input: str) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'show_existing_invoice',
                'invoice_analytics',
                'accounting_document_analytics',
                'add_receipt',
                'show_recent_accounting_documents',
                'unknown',
            ],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == 'accounting_document_analytics'

def test_process_invoice_text_runs_accounting_document_analytics_runtime_without_invoice_side_effects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'invoice_analytics' if kwargs['context_name'] == 'top_level_action' else 'unknown'

    async def _unexpected_invoice_planner(**kwargs) -> InvoiceAnalyticsPlan:
        raise AssertionError('outgoing invoice analytics planner must not run for receipt analytics')

    metadata_dir = tmp_path / 'workspaces' / 'telegram-111' / 'years' / '2026' / 'expenses' / '06' / 'receipts' / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / 'receipt-1.json').write_text(
        json.dumps(
            {
                'document_type': 'receipt',
                'business': {
                    'issue_date': '2026-06-10',
                    'vendor_name': 'BAUHAUS',
                    'total_amount': 13.83,
                    'currency': 'EUR',
                },
                'category': {
                    'category_id': 'material',
                    'label_snapshot': 'Materiál',
                    'source': 'confirmed_existing',
                },
            }
        ),
        encoding='utf-8',
    )

    planner_calls: list[dict] = []
    executor_calls: list[dict] = []

    async def _planner(**kwargs):
        planner_calls.append(kwargs)
        return SimpleNamespace(
            analysis_code="df = accounting_documents_df.copy()\nresult = {'summary': {'count': len(df)}}",
            answer_language='uk',
            reasoning_summary='Pocet bločkov.',
        )

    def _execute(**kwargs):
        executor_calls.append(kwargs)
        dataframe = kwargs['accounting_documents_df']
        assert len(dataframe) == 1
        assert dataframe.iloc[0]['vendor_name'] == 'BAUHAUS'
        assert dataframe.iloc[0]['category_id'] == 'material'
        return SimpleNamespace(result={'summary': {'count': 1, 'total': 13.83}}, warnings=())

    async def _answer(**kwargs) -> str:
        assert kwargs['answer_language'] == 'sk'
        assert kwargs['dataset_metadata']['row_count'] == 1
        return 'Našiel som 1 potvrdený bloček v sume 13.83 EUR.'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _unexpected_invoice_planner)
    monkeypatch.setattr('bot.handlers.invoice.plan_accounting_document_analytics_code', _planner)
    monkeypatch.setattr('bot.handlers.invoice.execute_accounting_document_analytics_code', _execute)
    monkeypatch.setattr('bot.handlers.invoice.answer_accounting_document_analytics', _answer)

    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    message = _authorized_message('Koľko som minul v BAUHAUS?', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert len(planner_calls) == 1
    assert len(executor_calls) == 1
    assert message.answers[-1] == 'Našiel som 1 potvrdený bloček v sume 13.83 EUR.'
    assert state.cleared is True
    assert message.documents == []
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []

@pytest.mark.parametrize(
    ('user_input', 'expected_action'),
    [
        ('Koľko som minul na palivo tento mesiac?', 'accounting_document_analytics'),
        ('Koľko bolo bločkov v kategórii materiál?', 'accounting_document_analytics'),
        ('Ukáž sumy podľa kategórií za jún', 'accounting_document_analytics'),
        ('Koľko som minul v BAUHAUS?', 'accounting_document_analytics'),
        ('Koľko mám prijatých faktúr za jún?', 'accounting_document_analytics'),
        ('Koľko mám vystavených faktúr za jún?', 'invoice_analytics'),
        ('Koľko som vystavil faktúr za jún?', 'invoice_analytics'),
        ('Top klientov podľa sumy faktúr', 'invoice_analytics'),
        ('Pridaj bloček', 'add_receipt'),
        ('Chcem nahrať prijatú faktúru', 'add_receipt'),
        ('Ukáž posledné bločky', 'show_recent_accounting_documents'),
        ('Otvor faktúru 04', 'show_existing_invoice'),
    ],
)
def test_smoke_analytics_action_boundaries_do_not_steal_existing_routes(
    user_input: str,
    expected_action: str,
) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=[
                'create_invoice',
                'show_existing_invoice',
                'invoice_analytics',
                'accounting_document_analytics',
                'add_receipt',
                'show_recent_accounting_documents',
                'unknown',
            ],
            user_input_text=user_input,
            api_key=None,
            model='gpt-4o',
        )
    ) == expected_action


@pytest.mark.parametrize(
    'user_input',
    [
        'Vieš spraviť DPH report z bločkov?',
        'Spočítaj daňovo uznateľné výdavky z bločkov.',
        'Porovnaj bločky s bankovými pohybmi.',
        'Exportuj výdavky z bločkov do účtovníctva.',
    ],
)
def test_smoke_unsupported_accounting_document_analytics_never_reaches_planner(
    tmp_path: Path,
    monkeypatch,
    user_input: str,
) -> None:
    async def _resolver(**kwargs) -> str:
        return 'accounting_document_analytics' if kwargs['context_name'] == 'top_level_action' else 'unknown'

    async def _unexpected_accounting_planner(**kwargs):
        raise AssertionError('accounting-document analytics planner must not run for bank/tax/export requests')

    async def _unexpected_invoice_planner(**kwargs) -> InvoiceAnalyticsPlan:
        raise AssertionError('invoice analytics planner must not run for bank/tax/export receipt requests')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.plan_accounting_document_analytics_code', _unexpected_accounting_planner)
    monkeypatch.setattr('bot.handlers.invoice.plan_invoice_analytics_code', _unexpected_invoice_planner)

    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    message = _authorized_message(user_input, telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == CustomizationRequestStates.waiting_preview_decision
    assert state.cleared is False
    draft = state.data['customization_request_draft']
    assert draft['source_capability_id'] == 'bank_cashflow_tax_analytics'
    assert draft['source_topic_id'] == 'bank_cashflow_tax_analytics'
    assert message.documents == []
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []


@pytest.mark.parametrize(
    ('user_input', 'expected_capability'),
    [
        ('Vieš analyzovať bločky?', 'receipt_analytics'),
        ('Vieš analyzovať bločky a prijaté faktúry?', 'accounting_document_analytics'),
        ('Vieš robiť analytiku vystavených faktúr?', 'invoice_analytics'),
        ('Vieš kategorizovať bločky?', 'accounting_document_categories'),
        ('Vieš DPH report z bločkov?', 'bank_cashflow_tax_analytics'),
    ],
)
def test_smoke_infohelp_distinguishes_analytics_capability_questions(
    user_input: str,
    expected_capability: str,
) -> None:
    from bot.services.info_help import classify_info_help_capability

    assert classify_info_help_capability(user_input_text=user_input) == expected_capability

def test_top_level_resolver_routes_mark_existing_invoice_paid_before_analytics() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'invoice_analytics', 'mark_existing_invoice_paid', 'unknown'],
            user_input_text='Oznac fakturu 06 ako uhradenu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'mark_existing_invoice_paid'

    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'invoice_analytics', 'mark_existing_invoice_paid', 'unknown'],
            user_input_text='Kolko mam uhradenych faktur?',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'invoice_analytics'


def test_process_invoice_text_mark_existing_invoice_paid_enters_confirmation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    invoice_id = InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        invoice_number='20260006',
        issue_date='2026-06-01',
        delivery_date='2026-06-01',
        due_date='2026-06-15',
        due_days=14,
        total_amount=100.0,
        currency='EUR',
        status='saved',
        contact_id=1,
        items=[
            CreateInvoiceItemPayload(
                description_raw='servis',
                description_normalized='Servis',
                item_description_raw=None,
                quantity=1.0,
                unit='ks',
                unit_price=100.0,
                total_price=100.0,
            )
        ],
    )
    assert invoice_id > 0
    message = _authorized_message('Oznac fakturu 06 ako uhradenu', telegram_id=111)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == InvoiceStates.waiting_mark_existing_invoice_paid_confirm
    assert state.data['pending_mark_paid_invoice_id'] == invoice_id
    assert state.data['pending_mark_paid_invoice_number'] == '20260006'
    assert any('bankove potvrdenie' in answer.lower() for answer in message.answers)


def test_invoice_analytics_explicit_unresolved_customer_fails_safe_before_planner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = _config_with_api_key(tmp_path)
    init_db(config.db_path)
    contacts = ContactService(config.db_path)
    contacts.create_contact(
        ContactProfile(
            supplier_telegram_id=111,
            name='Tech Company s.r.o.',
            ico='12345678',
            dic='1234567800',
            ic_dph=None,
            address='Hlavna 1, Kosice',
            email='',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    contact = contacts.get_by_name(111, 'Tech Company s.r.o.')
    assert contact is not None and contact.id is not None
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=contact.id,
        invoice_number='20260001',
        issue_date='2026-05-10',
        delivery_date='2026-05-10',
        due_date='2026-05-24',
        due_days=14,
        total_amount=300,
        currency='EUR',
        status='unpaid',
        items=[
            CreateInvoiceItemPayload(
                description_raw='oprava',
                description_normalized='Oprava',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=300,
                total_price=300,
            )
        ],
    )

    async def _extractor(**kwargs) -> str:
        return 'Невідома фірма'

    async def _resolver(**kwargs) -> str:
        if kwargs['context_name'] == 'top_level_action':
            return 'invoice_analytics'
        if kwargs['context_name'] == 'invoice_analytics_customer_resolution':
            assert kwargs['user_input_text'] == 'Невідома фірма'
            assert kwargs['allowed_actions'] == ['Tech Company s.r.o.']
            return 'unknown'
        return 'unknown'

    async def _unexpected_planner(**kwargs):
        raise AssertionError('planner must not run for an explicit unresolved customer')

    monkeypatch.setattr(
        'bot.handlers.invoice.extract_invoice_analytics_customer_reference',
        _extractor,
    )
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr(
        'bot.handlers.invoice.plan_invoice_analytics_code',
        _unexpected_planner,
    )

    message = _authorized_message(
        'Покажи суму фактур для Невідома фірма.',
        telegram_id=111,
    )
    state = _DummyState()

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text=message.text,
        )
    )

    assert state.cleared is True
    assert 'Невідома фірма' in message.answers[-1]
    assert 'nevedel jednoznačne priradiť' in message.answers[-1]
