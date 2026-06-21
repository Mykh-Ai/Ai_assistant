import asyncio
import inspect
import json

import pytest

from bot.services.info_help_resolver import (
    build_info_help_triage_payload,
    resolve_info_help_triage_with_llm,
)
from bot.services import info_help
from bot.services.info_help import (
    TRIAGE_ADMIN_REVIEW_CANDIDATE,
    TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE,
    TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
    TRIAGE_OUT_OF_DOMAIN,
    TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE,
    TRIAGE_SMALLTALK,
    TRIAGE_SPAM_OR_ABUSE,
    TRIAGE_UNCLEAR_NEEDS_CLARIFICATION,
    build_info_help_triage_guidance_with_llm,
    build_info_help_triage_guidance,
    build_product_truth_guidance,
    classify_info_help_capability,
    classify_info_help_triage,
    parse_info_help_triage_model_output,
)
from bot.services.product_truth import get_safe_answer_payload


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type('_Msg', (), {'content': content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _InfoHelpOpenAIFake:
    output = '{"capability_id":"unknown","topic_id":"unknown","triage_class":"unknown","confidence":0,"needs_clarification":false}'
    last_payload: dict | None = None
    last_system_prompt: str | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _InfoHelpOpenAIFake.last_system_prompt = kwargs['messages'][0]['content']
        _InfoHelpOpenAIFake.last_payload = json.loads(kwargs['messages'][1]['content'])
        return _FakeResponse(_InfoHelpOpenAIFake.output)


class _InfoHelpOpenAIErrorFake:
    def __init__(self, *, api_key: str) -> None:
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        raise RuntimeError('client failed')


class _InfoHelpOpenAIUnexpectedCallFake:
    def __init__(self, *, api_key: str) -> None:
        raise AssertionError('InfoHelp LLM client must not be instantiated')


class _InfoHelpOpenAISlowFake:
    def __init__(self, *, api_key: str) -> None:
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        await asyncio.sleep(1)
        return _FakeResponse(_InfoHelpOpenAIFake.output)


def test_email_capability_question_renders_unsupported_product_truth_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='Vieš poslať faktúru emailom?')

    assert answer is not None
    assert 'Odosielanie faktúr emailom' in answer
    assert 'nepodporované' in answer
    assert 'Automatické odosielanie faktúr emailom priamo z bota' in answer
    assert 'externé prístupy' in answer
    assert 'Preposlať' in answer
    assert 'Zdieľať' in answer or 'Stiahnuť' in answer
    assert 'adresu príjemcu aj text emailu vypĺňate ručne' in answer
    assert 'Ak chcete automatické odosielanie faktúr emailom priamo z bota' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer
    assert 'samostatný potvrdený náhľad' not in answer
    assert 'I emailed the invoice.' not in answer


def test_google_drive_question_renders_external_limitation() -> None:
    answer = build_product_truth_guidance(user_input_text='Vie bot ukladať faktúry na Google Drive?')

    assert answer is not None
    assert 'Ukladanie faktúr na Google Drive' in answer
    assert 'nepodporované' in answer
    assert 'externé prístupy' in answer


def test_invoice_due_date_reminder_question_renders_partial_automatic_status() -> None:
    answer = build_product_truth_guidance(user_input_text='Vieš mi pripomenúť neuhradené faktúry po splatnosti?')

    assert answer is not None
    assert 'Pripomienky faktúr po splatnosti' in answer
    assert 'čiastočné' in answer
    assert '/kontrola_splatnosti' not in answer
    assert 'background scheduler' in answer
    assert 'Google Drive' in answer
    assert 'nie sú zapnuté' in answer


def test_google_drive_after_due_date_archive_question_renders_stub_only_unsupported_status() -> None:
    answer = build_product_truth_guidance(
        user_input_text='Vieš archivovať zaplatené faktúry po splatnosti na Google Drive?'
    )

    assert answer is not None
    assert 'Archivácia faktúry na Google Drive po splatnosti' in answer
    assert 'nepodporované' in answer
    assert 'iba lokálny stub' in answer
    assert 'nič sa nenahráva na Google Drive' in answer
    assert 'úspešné nahratie' in answer
    assert 'uploaded' not in answer.lower()


def test_sms_question_renders_external_limitation() -> None:
    answer = build_product_truth_guidance(user_input_text='Viete posielať SMS pripomienky?')

    assert answer is not None
    assert 'SMS pripomienky' in answer
    assert 'nepodporované' in answer
    assert 'externé prístupy' in answer


def test_custom_pdf_template_question_renders_safe_customization_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='Can you use my old PDF template?')

    assert answer is not None
    assert 'Vlastná PDF šablóna faktúry' in answer
    assert 'nepodporované' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer
    assert 'samostatný potvrdený náhľad' not in answer
    assert 'Your custom invoice template is already active.' not in answer


def test_what_can_you_do_renders_bounded_product_truth_overview() -> None:
    answer = build_product_truth_guidance(user_input_text='What can you do?')

    assert answer is not None
    assert 'Overený prehľad podľa Product Truth' in answer
    assert 'vytvorenie faktúry: podporované' in answer
    assert 'odosielanie faktúr emailom: nepodporované' in answer
    assert '/menu' not in answer


def test_create_invoice_how_to_renders_supported_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='How do I create an invoice?')

    assert answer is not None
    assert 'Vytvorenie faktúry' in answer
    assert 'podporované' in answer
    assert '/invoice' in answer
    assert 'nepodporovanú alebo nejasnú potrebu' not in answer
    assert 'požiadavku na kontrolu správcom' not in answer


def test_add_receipt_how_to_renders_partial_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='Ako pridám bloček?')

    assert answer is not None
    assert 'Pridanie bločku alebo prijatej faktúry' in answer
    assert 'čiastočné' in answer
    assert 'fotka alebo PDF' in answer
    assert 'nepodporovanú alebo nejasnú potrebu' not in answer
    assert 'požiadavku na kontrolu správcom' not in answer


def test_voice_limitation_question_renders_partial_text_first_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='Môžem diktovať faktúru hlasom aj s presnou sumou?')

    assert answer is not None
    assert 'Hlasové zadanie faktúry' in answer
    assert 'čiastočné' in answer
    assert 'textu alebo súboru' in answer


def test_delete_database_question_renders_safety_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='Ako môžem vymazať databázu?')

    assert answer is not None
    assert 'Vymazanie používateľskej databázy' in answer
    assert 'podporované' in answer
    assert 'citlivá alebo deštruktívna' in answer
    assert 'presnú napísanú frázu' in answer


def test_accounting_export_smoke_phrase_renders_product_truth_guidance() -> None:
    assert (
        classify_info_help_capability(user_input_text='Vieš exportovať podklady pre účtovníctvo?')
        == 'accounting_export'
    )
    answer = build_product_truth_guidance(user_input_text='Vieš exportovať podklady pre účtovníctvo?')

    assert answer is not None
    assert 'Export do účtovníctva' in answer
    assert 'nepodporované' in answer
    assert 'externé prístupy' in answer


def test_custom_pdf_template_smoke_phrase_renders_product_truth_guidance() -> None:
    assert (
        classify_info_help_capability(user_input_text='Môžem si upraviť PDF šablónu?')
        == 'invoice_pdf_custom_template'
    )
    answer = build_product_truth_guidance(user_input_text='Môžem si upraviť PDF šablónu?')

    assert answer is not None
    assert 'Vlastná PDF šablóna faktúry' in answer
    assert 'nepodporované' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'samostatný potvrdený náhľad' not in answer


def test_custom_function_smoke_phrase_renders_product_truth_guidance() -> None:
    assert classify_info_help_capability(user_input_text='Chcem vlastnú funkciu') == 'customization_requests'
    answer = build_product_truth_guidance(user_input_text='Chcem vlastnú funkciu')

    assert answer is not None
    assert 'Požiadavky na úpravu' in answer
    assert 'čiastočné' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer
    assert 'automatickú implementáciu' in answer
    assert 'Complete Level 3' not in answer


def test_info_help_answers_human_review_request_lifecycle() -> None:
    answer = build_product_truth_guidance(user_input_text='Ako funguje moja požiadavka?')

    assert answer is not None
    assert 'Požiadavky na úpravu' in answer
    assert 'čiastočné' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer
    assert 'automatickú implementáciu' in answer


def test_info_help_answers_admin_response_to_user() -> None:
    answer = build_product_truth_guidance(user_input_text='Ako mi odpovie správca?')

    assert answer is not None
    assert 'Odpoveď správcu používateľovi' in answer
    assert 'jednu odpoveď' in answer
    assert 'nemení Product Truth' in answer
    assert 'garantované' not in answer.lower()


def test_info_help_explains_accepted_rejected_request_status_only() -> None:
    accepted = build_product_truth_guidance(user_input_text='Čo znamená prijatá požiadavka?')
    rejected = build_product_truth_guidance(user_input_text='Čo znamená zamietnutá požiadavka?')

    assert accepted is not None
    assert rejected is not None
    for answer in (accepted, rejected):
        assert 'Posúdenie požiadavky správcom' in answer
        assert 'nie je sľub implementácie' in answer
        assert 'zmenu schopností produktu' in answer


def test_info_help_explains_unknown_question_can_use_confirmed_admin_review_flow() -> None:
    answer = build_product_truth_guidance(user_input_text='Čo sa stane, keď bot nevie odpovedať?')
    admin_question = build_product_truth_guidance(user_input_text='Môžem poslať otázku správcovi?')

    assert answer is not None
    assert admin_question is not None
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'požiadavku na kontrolu správcom' in admin_question
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer
    assert 'samostatný potvrdený náhľad' not in answer
    assert 'nič neukladá' not in answer
    assert 'automatickú implementáciu' in admin_question


def test_info_help_explains_delivery_observability_is_admin_facing() -> None:
    answer = build_product_truth_guidance(user_input_text='Ako zistím, či bola odpoveď správcu doručená?')

    assert answer is not None
    assert 'Stav doručenia odpovede správcu' in answer
    assert 'admin-facing' in answer
    assert 'automatické opakovanie' in answer


def test_info_help_answers_existing_runtime_how_tos() -> None:
    examples = {
        'Ako zobrazím posledné bločky?': 'Posledné bločky a účtovné doklady',
        'Ako pridám kontakt?': 'Kontakty',
        'Ako pridám službu?': 'Služby a položky',
        'Ako upravím existujúcu faktúru?': 'Úprava existujúcej faktúry',
        'Ako vymažem jednu faktúru?': 'Vymazanie jednej faktúry',
        'Môžem diktovať hlasom?': 'Hlasové zadanie faktúry',
    }

    for question, expected_title in examples.items():
        answer = build_product_truth_guidance(user_input_text=question)
        assert answer is not None, question
        assert expected_title in answer
        assert 'nepodporovanú alebo nejasnú potrebu' not in answer
        assert 'požiadavku na kontrolu správcom' not in answer


def test_unsupported_capability_uses_user_friendly_admin_review_offer() -> None:
    answer = build_product_truth_guidance(user_input_text='Viete posielať SMS pripomienky?')

    assert answer is not None
    assert 'SMS pripomienky' in answer
    assert 'nepodporované' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer
    assert 'samostatný potvrdený náhľad' not in answer


def test_code_agent_handoff_smoke_phrase_renders_product_truth_guidance() -> None:
    assert (
        classify_info_help_capability(user_input_text='Vieš odovzdať úlohu code agentovi?')
        == 'code_agent_handoff'
    )
    answer = build_product_truth_guidance(user_input_text='Vieš odovzdať úlohu code agentovi?')

    assert answer is not None
    assert 'Odovzdanie úlohy kódovaciemu agentovi' in answer
    assert 'nepodporované' in answer
    assert 'vyžaduje správcu' in answer
    assert 'citlivá alebo deštruktívna' in answer


def test_delete_database_smoke_phrase_renders_safety_guidance() -> None:
    assert classify_info_help_capability(user_input_text='Ako vymažem databázu?') == 'delete_user_database'
    answer = build_product_truth_guidance(user_input_text='Ako vymažem databázu?')

    assert answer is not None
    assert 'Vymazanie používateľskej databázy' in answer
    assert 'podporované' in answer
    assert 'citlivá alebo deštruktívna' in answer


def test_ambiguous_direct_invoice_text_is_not_info_help() -> None:
    assert classify_info_help_capability(user_input_text='Vytvor faktúru pre ABC za opravu 100 eur') is None


def test_info_help_llm_payload_contains_only_classification_fields() -> None:
    payload = build_info_help_triage_payload(
        user_input_text='Chcem dashboard cashflow.',
        input_channel='voice',
    )

    assert payload['context_name'] == 'info_help_triage'
    assert payload['input_channel'] == 'voice'
    assert payload['request_storage_available'] is True
    assert payload['admin_notification_available'] is False
    assert set(payload['expected_output']) == {
        'capability_id',
        'topic_id',
        'triage_class',
        'confidence',
        'needs_clarification',
    }

    forbidden_keys = {
        'primary_status',
        'response_mode',
        'safe_next',
        'safe_next_steps',
        'forbidden_claims',
        'answer_text',
        'canonical_action',
        'request_draft',
        'admin_message',
    }
    assert forbidden_keys.isdisjoint(payload)
    assert payload['known_capabilities']
    for capability in payload['known_capabilities']:
        assert set(capability) == {'capability_id', 'title', 'domain', 'classification_summary'}
        assert forbidden_keys.isdisjoint(capability)


def test_triage_model_output_rejects_invented_capability_id() -> None:
    result = parse_info_help_triage_model_output(
        '{"capability_id":"magic_export","triage_class":"known_product_capability","topic_id":"product_capability"}'
    )

    assert result.capability_id == 'unknown'
    assert result.triage_class == 'unknown'


def test_triage_model_output_invalid_json_is_unknown() -> None:
    result = parse_info_help_triage_model_output('not json')

    assert result.capability_id == 'unknown'
    assert result.topic_id == 'unknown'
    assert result.triage_class == 'unknown'


def test_triage_model_output_rejects_unsupported_triage_class() -> None:
    result = parse_info_help_triage_model_output(
        '{"capability_id":"unknown","triage_class":"invented_class","topic_id":"admin_review"}'
    )

    assert result.capability_id == 'unknown'
    assert result.triage_class == 'unknown'
    assert result.topic_id == 'unknown'


def test_triage_model_output_non_object_json_is_unknown() -> None:
    result = parse_info_help_triage_model_output('["send_invoice_email"]')

    assert result == info_help.InfoHelpTriageResult()


def test_triage_model_output_confidence_is_bounded_and_safe() -> None:
    high = parse_info_help_triage_model_output(
        '{"capability_id":"unknown","triage_class":"smalltalk","confidence":9.5}'
    )
    low = parse_info_help_triage_model_output(
        '{"capability_id":"unknown","triage_class":"smalltalk","confidence":-2}'
    )
    non_numeric = parse_info_help_triage_model_output(
        '{"capability_id":"unknown","triage_class":"smalltalk","confidence":"very sure"}'
    )

    assert high.confidence == 1.0
    assert low.confidence == 0.0
    assert non_numeric.confidence == 0.0


def test_triage_model_output_unknown_topic_id_falls_back_safely() -> None:
    result = parse_info_help_triage_model_output(
        (
            '{"capability_id":"unknown",'
            '"triage_class":"new_business_feature_request",'
            '"topic_id":"trusted_product_truth",'
            '"confidence":0.7}'
        )
    )

    assert result.capability_id == 'unknown'
    assert result.triage_class == TRIAGE_NEW_BUSINESS_FEATURE_REQUEST
    assert result.topic_id == 'new_business_feature'


def test_triage_model_output_known_capability_invalid_topic_normalizes_safely() -> None:
    result = parse_info_help_triage_model_output(
        (
            '{"capability_id":"send_invoice_email",'
            '"triage_class":"known_product_capability",'
            '"topic_id":"invented_trusted_topic",'
            '"confidence":0.7}'
        )
    )

    assert result.capability_id == 'send_invoice_email'
    assert result.triage_class == 'known_product_capability'
    assert result.topic_id == 'product_capability'


def test_triage_model_output_ignores_answer_text_status_and_response_mode() -> None:
    result = parse_info_help_triage_model_output(
        (
            '{"capability_id":"send_invoice_email",'
            '"triage_class":"known_product_capability",'
            '"topic_id":"product_capability",'
            '"answer_text":"I can send it now",'
            '"primary_status":"supported",'
            '"support_status":"supported",'
            '"response_mode":"offer_linked_action"}'
        )
    )

    assert result.capability_id == 'send_invoice_email'
    assert result.triage_class == 'known_product_capability'
    assert not hasattr(result, 'answer_text')
    assert not hasattr(result, 'primary_status')
    assert not hasattr(result, 'response_mode')


def test_triage_model_output_conflicting_known_capability_and_triage_fails_safe() -> None:
    result = parse_info_help_triage_model_output(
        (
            '{"capability_id":"send_invoice_email",'
            '"triage_class":"out_of_domain",'
            '"topic_id":"out_of_domain",'
            '"confidence":0.9}'
        )
    )

    assert result == info_help.InfoHelpTriageResult()


def test_response_mode_and_primary_status_do_not_override_product_truth_rendering() -> None:
    result = parse_info_help_triage_model_output(
        (
            '{"capability_id":"send_invoice_email",'
            '"triage_class":"known_product_capability",'
            '"topic_id":"product_capability",'
            '"primary_status":"supported",'
            '"response_mode":"explain_supported_usage",'
            '"answer_text":"I can send this invoice now."}'
        )
    )
    answer = build_info_help_triage_guidance(user_input_text='Vie\u0161 posla\u0165 fakt\u00faru emailom?')

    assert result.capability_id == 'send_invoice_email'
    assert answer is not None
    assert 'Odosielanie fakt\u00far emailom' in answer
    assert 'nepodporovan\u00e9' in answer
    assert 'I can send this invoice now.' not in answer


def test_triage_model_output_rejects_free_form_answer_only() -> None:
    result = parse_info_help_triage_model_output('{"answer_text":"Sure, I can do that."}')

    assert result == info_help.InfoHelpTriageResult()


def test_triage_model_output_ignores_side_effect_and_action_fields() -> None:
    result = parse_info_help_triage_model_output(
        (
            '{"capability_id":"unknown",'
            '"triage_class":"admin_review_candidate",'
            '"topic_id":"admin_review",'
            '"canonical_action":"create_invoice",'
            '"request_draft":{"title":"Save this"},'
            '"admin_message":"Please notify admin"}'
        )
    )

    assert result.triage_class == TRIAGE_ADMIN_REVIEW_CANDIDATE
    assert not hasattr(result, 'canonical_action')
    assert not hasattr(result, 'request_draft')
    assert not hasattr(result, 'admin_message')


@pytest.mark.parametrize(
    ('model_output', 'expected_capability', 'expected_triage', 'expected_topic'),
    [
        (
            {
                'capability_id': 'send_invoice_email',
                'topic_id': 'product_capability',
                'triage_class': 'known_product_capability',
                'confidence': 0.91,
                'needs_clarification': False,
            },
            'send_invoice_email',
            'known_product_capability',
            'product_capability',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'new_business_feature',
                'triage_class': 'new_business_feature_request',
                'confidence': 0.8,
                'needs_clarification': False,
            },
            'unknown',
            TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
            'new_business_feature',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'customization_request',
                'triage_class': 'customization_request_candidate',
                'confidence': 0.8,
                'needs_clarification': False,
            },
            'unknown',
            TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE,
            'customization_request',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'admin_review',
                'triage_class': 'admin_review_candidate',
                'confidence': 0.8,
                'needs_clarification': False,
            },
            'unknown',
            TRIAGE_ADMIN_REVIEW_CANDIDATE,
            'admin_review',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'out_of_domain',
                'triage_class': 'out_of_domain',
                'confidence': 0.8,
                'needs_clarification': False,
            },
            'unknown',
            TRIAGE_OUT_OF_DOMAIN,
            'out_of_domain',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'spam_or_abuse',
                'triage_class': 'spam_or_abuse',
                'confidence': 0.8,
                'needs_clarification': False,
            },
            'unknown',
            TRIAGE_SPAM_OR_ABUSE,
            'spam_or_abuse',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'smalltalk',
                'triage_class': 'smalltalk',
                'confidence': 0.8,
                'needs_clarification': False,
            },
            'unknown',
            TRIAGE_SMALLTALK,
            'smalltalk',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'clarification',
                'triage_class': 'unclear_needs_clarification',
                'confidence': 0.8,
                'needs_clarification': True,
            },
            'unknown',
            TRIAGE_UNCLEAR_NEEDS_CLARIFICATION,
            'clarification',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'possible_product_truth_candidate',
                'triage_class': 'possible_product_truth_candidate',
                'confidence': 0.6,
                'needs_clarification': False,
            },
            'unknown',
            TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE,
            'possible_product_truth_candidate',
        ),
        (
            {
                'capability_id': 'unknown',
                'topic_id': 'unknown',
                'triage_class': 'unknown',
                'confidence': 0.0,
                'needs_clarification': False,
            },
            'unknown',
            'unknown',
            'unknown',
        ),
    ],
)
def test_llm_info_help_triage_classifier_valid_outputs(
    monkeypatch,
    model_output: dict,
    expected_capability: str,
    expected_triage: str,
    expected_topic: str,
) -> None:
    _InfoHelpOpenAIFake.output = json.dumps(model_output)
    _InfoHelpOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIFake)

    result = asyncio.run(
        resolve_info_help_triage_with_llm(
            user_input_text='neznama poziadavka',
            api_key='sk-test',
            model='gpt-4o',
        )
    )

    assert result.capability_id == expected_capability
    assert result.triage_class == expected_triage
    assert result.topic_id == expected_topic
    assert _InfoHelpOpenAIFake.last_payload is not None
    assert set(_InfoHelpOpenAIFake.last_payload['expected_output']) == {
        'capability_id',
        'topic_id',
        'triage_class',
        'confidence',
        'needs_clarification',
    }


def test_llm_info_help_triage_no_api_key_is_safe_unknown(monkeypatch) -> None:
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIUnexpectedCallFake)

    result = asyncio.run(
        resolve_info_help_triage_with_llm(
            user_input_text='cashflow dashboard',
            api_key=None,
            model='gpt-4o',
        )
    )

    assert result == info_help.InfoHelpTriageResult()


def test_llm_info_help_triage_non_sk_api_key_is_safe_unknown_without_client_call(monkeypatch) -> None:
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIUnexpectedCallFake)

    result = asyncio.run(
        resolve_info_help_triage_with_llm(
            user_input_text='cashflow dashboard',
            api_key='not-a-real-key',
            model='gpt-4o',
        )
    )

    assert result == info_help.InfoHelpTriageResult()


def test_llm_info_help_triage_client_exception_is_safe_unknown(monkeypatch) -> None:
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIErrorFake)

    result = asyncio.run(
        resolve_info_help_triage_with_llm(
            user_input_text='cashflow dashboard',
            api_key='sk-test',
            model='gpt-4o',
        )
    )

    assert result == info_help.InfoHelpTriageResult()


def test_llm_info_help_triage_timeout_is_safe_unknown(monkeypatch) -> None:
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAISlowFake)

    result = asyncio.run(
        resolve_info_help_triage_with_llm(
            user_input_text='cashflow dashboard',
            api_key='sk-test',
            model='gpt-4o',
            timeout_seconds=0.001,
        )
    )

    assert result == info_help.InfoHelpTriageResult()


def test_llm_response_mode_and_status_do_not_override_product_truth_rendering(monkeypatch) -> None:
    _InfoHelpOpenAIFake.output = json.dumps(
        {
            'capability_id': 'send_invoice_email',
            'topic_id': 'product_capability',
            'triage_class': 'known_product_capability',
            'confidence': 0.91,
            'needs_clarification': False,
            'primary_status': 'supported',
            'response_mode': 'explain_supported_usage',
            'answer_text': 'I can send this invoice now.',
        }
    )
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIFake)

    answer = asyncio.run(
        build_info_help_triage_guidance_with_llm(
            user_input_text='viete to dorucit klientovi digitalne?',
            api_key='sk-test',
            model='gpt-4o',
        )
    )

    assert answer is not None
    assert 'Odosielanie fakt\u00far emailom' in answer
    assert 'nepodporovan\u00e9' in answer
    assert 'I can send this invoice now.' not in answer


def test_llm_unknown_classification_returns_no_triage_answer(monkeypatch) -> None:
    _InfoHelpOpenAIFake.output = json.dumps(
        {
            'capability_id': 'unknown',
            'topic_id': 'unknown',
            'triage_class': 'unknown',
            'confidence': 0.0,
            'needs_clarification': False,
        }
    )
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIFake)

    answer = asyncio.run(
        build_info_help_triage_guidance_with_llm(
            user_input_text='nejasny dashboard maybe',
            api_key='sk-test',
            model='gpt-4o',
        )
    )

    assert answer is None


def test_llm_possible_product_truth_candidate_renders_clarification(monkeypatch) -> None:
    _InfoHelpOpenAIFake.output = json.dumps(
        {
            'capability_id': 'unknown',
            'topic_id': 'possible_product_truth_candidate',
            'triage_class': 'possible_product_truth_candidate',
            'confidence': 0.61,
            'needs_clarification': False,
        }
    )
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIFake)

    answer = asyncio.run(
        build_info_help_triage_guidance_with_llm(
            user_input_text='viete spravit veci okolo workflow?',
            api_key='sk-test',
            model='gpt-4o',
        )
    )

    assert answer is not None
    assert 'neviem ju bezpe\u010dne priradi\u0165' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer
    assert 'Product Truth sa tým automaticky nemení' in answer


@pytest.mark.parametrize(
    ('user_input', 'model_output', 'expected_triage'),
    [
        (
            'Potrebujem nový typ prehľadu tržieb',
            {
                'capability_id': 'unknown',
                'topic_id': 'new_business_feature',
                'triage_class': 'new_business_feature_request',
                'confidence': 0.8,
                'needs_clarification': False,
            },
            TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
        ),
        (
            'Vies spravit novy dashboard trzby pls',
            {
                'capability_id': 'unknown',
                'topic_id': 'new_business_feature',
                'triage_class': 'new_business_feature_request',
                'confidence': 0.78,
                'needs_clarification': False,
            },
            TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
        ),
        (
            '\u0427\u0438 \u043c\u043e\u0436\u0435\u0448 \u0437\u0440\u043e\u0431\u0438\u0442\u0438 \u043d\u043e\u0432\u0438\u0439 \u0437\u0432\u0456\u0442?',
            {
                'capability_id': 'unknown',
                'topic_id': 'new_business_feature',
                'triage_class': 'new_business_feature_request',
                'confidence': 0.76,
                'needs_clarification': False,
            },
            TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
        ),
        (
            '\u041f\u043e\u0433\u043e\u0434\u0430 \u0437\u0430\u0432\u0442\u0440\u0430?',
            {
                'capability_id': 'unknown',
                'topic_id': 'out_of_domain',
                'triage_class': 'out_of_domain',
                'confidence': 0.82,
                'needs_clarification': False,
            },
            TRIAGE_OUT_OF_DOMAIN,
        ),
        (
            'treba report trzieb \u0431\u0443\u0434\u044c \u043b\u0430\u0441\u043a\u0430 hmm',
            {
                'capability_id': 'unknown',
                'topic_id': 'new_business_feature',
                'triage_class': 'new_business_feature_request',
                'confidence': 0.72,
                'needs_clarification': False,
            },
            TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
        ),
        (
            'em chcem asi nejaky prehlad trzby no',
            {
                'capability_id': 'unknown',
                'topic_id': 'new_business_feature',
                'triage_class': 'new_business_feature_request',
                'confidence': 0.66,
                'needs_clarification': False,
            },
            TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
        ),
    ],
)
def test_llm_info_help_triage_multilingual_noisy_payload_smoke(
    monkeypatch,
    user_input: str,
    model_output: dict,
    expected_triage: str,
) -> None:
    _InfoHelpOpenAIFake.output = json.dumps(model_output)
    _InfoHelpOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _InfoHelpOpenAIFake)

    result = asyncio.run(
        resolve_info_help_triage_with_llm(
            user_input_text=user_input,
            api_key='sk-test',
            model='gpt-4o',
        )
    )

    assert result.triage_class == expected_triage
    assert _InfoHelpOpenAIFake.last_payload is not None
    assert _InfoHelpOpenAIFake.last_payload['user_input_text'] == user_input


def test_info_help_triage_known_product_truth_email_question() -> None:
    result = classify_info_help_triage(user_input_text='Vie\u0161 posla\u0165 fakt\u00faru emailom?')

    assert result.capability_id == 'send_invoice_email'
    assert result.triage_class == 'known_product_capability'


def test_info_help_triage_business_feature_request() -> None:
    text = 'Vie\u0161 mi spravi\u0165 preh\u013ead tr\u017eieb za minul\u00fd mesiac?'
    result = classify_info_help_triage(user_input_text=text)

    assert result.triage_class == TRIAGE_NEW_BUSINESS_FEATURE_REQUEST
    answer = build_info_help_triage_guidance(user_input_text=text)
    assert answer is not None
    assert 'po\u017eiadavka na nov\u00fa biznis funkciu' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer


@pytest.mark.parametrize(
    'user_input',
    [
        'Na akú sumu som vystavil faktúry v tomto roku?',
        'Koľko som vystavil faktúr tento rok?',
        'Súhrn faktúr za 2026',
        'На яку суму я вже виставив фактуру в цьому році?',
        'На какую сумму я выставил фактур в этом году?',
        'На якую суму я выставіў фактур у гэтым годзе?',
    ],
)
def test_direct_yearly_invoice_summary_request_is_invoice_analytics_capability(user_input: str) -> None:
    assert build_product_truth_guidance(user_input_text=user_input) is None

    result = classify_info_help_triage(user_input_text=user_input)

    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'invoice_analytics'
    assert result.business_need == ''


def test_invoice_period_summary_capability_question_renders_supported_product_truth() -> None:
    answer = build_product_truth_guidance(user_input_text='Vieš spočítať súhrn faktúr za 2026?')

    assert answer is not None
    assert 'Analytika vystavených faktúr' in answer
    assert 'čiastočné' in answer
    assert 'read-only pilot' in answer
    assert 'uloženými odoslanými faktúrami' in answer

    result = classify_info_help_triage(user_input_text='Vieš spočítať súhrn faktúr za 2026?')
    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'invoice_analytics'


def test_invoice_analytics_capability_question_renders_partial_product_truth() -> None:
    answer = build_product_truth_guidance(user_input_text='Vieš robiť analytiku faktúr?')

    assert answer is not None
    assert 'Analytika vystavených faktúr' in answer
    assert 'čiastočné' in answer
    assert 'read-only pilot' in answer
    assert 'uloženými odoslanými faktúrami' in answer
    assert 'normalizovaný stav úhrady' in answer
    assert 'surový lifecycle status' in answer
    assert 'bankové pohyby' in answer
    assert 'nič nemení v databáze' in answer
    assert '/menu' not in answer

    result = classify_info_help_triage(user_input_text='Vieš robiť analytiku faktúr?')
    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'invoice_analytics'


@pytest.mark.parametrize(
    'user_input',
    [
        'Vieš analyzovať bločky?',
        'vydavky podla kategorii z blockov',
        'receipt analytics',
        '\u0430\u043d\u0430\u043b\u0456\u0442\u0438\u043a\u0430 \u0447\u0435\u043a\u0456\u0432',
        '\u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457 \u0447\u0435\u043a\u0456\u0432',
        '\u0430\u043d\u0430\u043b\u0438\u0442\u0438\u043a\u0430 \u0447\u0435\u043a\u043e\u0432',
    ],
)
def test_receipt_analytics_questions_render_partial_runtime_answer(user_input: str) -> None:
    assert classify_info_help_capability(user_input_text=user_input) == 'receipt_analytics'

    result = classify_info_help_triage(user_input_text=user_input)
    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'receipt_analytics'

    answer = build_product_truth_guidance(user_input_text=user_input)
    assert answer is not None
    assert 'Analytika bločkov' in answer
    assert 'čiastočné' in answer
    assert 'read-only runtime' in answer
    assert 'DPH' in answer
    assert 'Analytika vystavených faktúr' not in answer
    assert '/add_blocek' not in answer
    assert '\u0430\u043d\u0430\u043b' not in answer

@pytest.mark.parametrize(
    'user_input',
    [
        'Vieš analyzovať bločky a prijaté faktúry?',
        'Vieš robiť analytiku prijatých faktúr?',
        'výdavky podľa kategórií z účtovných dokladov',
    ],
)
def test_accounting_document_analytics_questions_render_partial_product_truth(user_input: str) -> None:
    assert classify_info_help_capability(user_input_text=user_input) == 'accounting_document_analytics'

    result = classify_info_help_triage(user_input_text=user_input)
    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'accounting_document_analytics'

    answer = build_product_truth_guidance(user_input_text=user_input)
    assert answer is not None
    assert 'Analytika bločkov a prijatých faktúr' in answer
    assert 'čiastočné' in answer
    assert 'read-only pilot' in answer
    assert 'banku' in answer or 'cashflow' in answer
    assert 'Analytika vystavených faktúr' not in answer


@pytest.mark.parametrize(
    'user_input',
    [
        'Vies kategorizovat blocky?',
        'Viete priradiť kategóriu bločku?',
        'Can you categorize receipts?',
    ],
)
def test_accounting_document_category_questions_render_partial_product_truth(user_input: str) -> None:
    assert classify_info_help_capability(user_input_text=user_input) == 'accounting_document_categories'

    result = classify_info_help_triage(user_input_text=user_input)
    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'accounting_document_categories'

    answer = build_product_truth_guidance(user_input_text=user_input)
    assert answer is not None
    assert 'Kategórie bločkov a prijatých faktúr' in answer
    assert 'čiastočné' in answer
    assert 'Nie je to samostatná top-level akcia' in answer
    assert 'Python validuje' in answer
    assert 'Analytika bločkov' not in answer


def test_receipt_analytics_question_is_not_routed_as_upload_receipt_how_to() -> None:
    assert classify_info_help_capability(user_input_text='Ako pridám bloček?') == 'add_receipt_or_incoming_invoice'
    assert classify_info_help_capability(user_input_text='Vieš analyzovať bločky?') == 'receipt_analytics'
    assert classify_info_help_capability(user_input_text='Vieš kategorizovať bločky?') == 'accounting_document_categories'


@pytest.mark.parametrize(
    'user_input',
    [
        'Vieš robiť cashflow?',
        'Vieš analyzovať banku?',
        'Vieš DPH report?',
        'Vieš robiť daňovú analytiku?',
    ],
)
def test_bank_cashflow_tax_questions_render_unsupported_answer(user_input: str) -> None:
    assert classify_info_help_capability(user_input_text=user_input) == 'bank_cashflow_tax_analytics'

    result = classify_info_help_triage(user_input_text=user_input)
    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'bank_cashflow_tax_analytics'

    answer = build_product_truth_guidance(user_input_text=user_input)
    assert answer is not None
    assert 'Banková, cashflow, DPH a daňová analytika' in answer
    assert 'nepodporované' in answer
    assert 'bankové výpisy' in answer
    assert 'DPH report' in answer
    assert 'daňové poradenstvo' in answer


def test_invoice_analytics_direct_runtime_request_is_known_capability_not_new_feature() -> None:
    result = classify_info_help_triage(user_input_text='Koľko mám neuhradených faktúr?')

    assert result.triage_class == 'known_product_capability'
    assert result.capability_id == 'invoice_analytics'


def test_product_truth_renderer_uses_payload_fields_when_localized_copy_is_missing() -> None:
    answer = info_help._render_product_truth_payload(get_safe_answer_payload('invoice_pdf_generation'))

    assert 'Invoice PDF generation: podporované.' in answer
    assert 'Táto schopnosť' not in answer
    assert 'Generates invoice PDFs' in answer
    assert 'Use the approved invoice flow' in answer


def test_unknown_product_truth_renderer_does_not_collapse_to_supported_generic_title() -> None:
    answer = info_help._render_product_truth_payload(get_safe_answer_payload('invoice_year_summary'))

    assert 'Unknown capability: neznáme.' in answer
    assert 'Táto schopnosť' not in answer
    assert 'podporované' not in answer
    assert 'Product Truth has no verified entry' in answer


def test_info_help_triage_out_of_domain_weather() -> None:
    result = classify_info_help_triage(user_input_text='Ak\u00e9 bude po\u010dasie zajtra?')

    assert result.triage_class == TRIAGE_OUT_OF_DOMAIN
    answer = build_info_help_triage_guidance(user_input_text='Ak\u00e9 bude po\u010dasie zajtra?')
    assert answer is not None
    assert 'mimo rozsahu OfficeFlow' in answer


def test_info_help_triage_random_junk_is_safe() -> None:
    result = classify_info_help_triage(user_input_text='@@@ #### !!!')

    assert result.triage_class == TRIAGE_SPAM_OR_ABUSE
    assert build_info_help_triage_guidance(user_input_text='@@@ #### !!!') is not None


def test_info_help_triage_smalltalk_redirects_to_business_scope() -> None:
    result = classify_info_help_triage(user_input_text='Ako sa m\u00e1\u0161?')

    assert result.triage_class == TRIAGE_SMALLTALK
    answer = build_info_help_triage_guidance(user_input_text='Ako sa m\u00e1\u0161?')
    assert answer is not None
    assert 'biznis \u00falohami' in answer


def test_info_help_triage_unclear_needs_clarification() -> None:
    result = classify_info_help_triage(user_input_text='urob mi to')

    assert result.triage_class == TRIAGE_UNCLEAR_NEEDS_CLARIFICATION
    assert result.needs_clarification is True
    answer = build_info_help_triage_guidance(user_input_text='urob mi to')
    assert answer is not None
    assert 'Nie je jasn\u00e9' in answer


def test_info_help_triage_admin_request_does_not_claim_send_or_save() -> None:
    text = 'Povedz adminovi, \u017ee potrebujem automatick\u00e9 pripomienky nezaplaten\u00fdch fakt\u00far.'
    result = classify_info_help_triage(user_input_text=text)

    assert result.triage_class == TRIAGE_ADMIN_REVIEW_CANDIDATE
    answer = build_info_help_triage_guidance(user_input_text=text)
    assert answer is not None
    assert 'Automatické odoslanie správcovi nie je zapnuté' in answer
    assert 'požiadavku na kontrolu správcom' in answer
    assert 'Uloží sa iba vtedy, keď ju potvrdíte.' in answer


def test_multilingual_and_noisy_triage_examples() -> None:
    assert classify_info_help_triage(user_input_text='Vies poslat fakturu emailom?').capability_id == 'send_invoice_email'
    assert classify_info_help_triage(user_input_text='\u0427\u0438 \u043c\u043e\u0436\u043d\u0430 \u0437\u0431\u0435\u0440\u0456\u0433\u0430\u0442\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0438 \u043d\u0430 Google Drive?').capability_id == 'google_drive_invoice_storage'
    assert classify_info_help_triage(user_input_text='\u041c\u043e\u0436\u043d\u043e \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0442\u044c SMS \u043d\u0430\u043f\u043e\u043c\u0438\u043d\u0430\u043d\u0438\u044f?').capability_id == 'sms_reminders'
    assert classify_info_help_triage(user_input_text='\u0430\u043d\u0430\u043b\u0456\u0442\u0438\u043a\u0430 \u0447\u0435\u043a\u0456\u0432').capability_id == 'receipt_analytics'
    assert (
        classify_info_help_triage(user_input_text='Treba mesacny report trzieb, no tak trochu').triage_class
        == TRIAGE_NEW_BUSINESS_FEATURE_REQUEST
    )


def test_multilingual_noisy_triage_matrix_extends_discovery_smoke() -> None:
    examples = [
        ('Vie\u0161 mi spravi\u0165 preh\u013ead tr\u017eieb za minul\u00fd mesiac?', TRIAGE_NEW_BUSINESS_FEATURE_REQUEST),
        ('Vies poslat fakturu emailom?', 'send_invoice_email'),
        ('\u042f\u043a\u0430 \u0431\u0443\u0434\u0435 \u043f\u043e\u0433\u043e\u0434\u0430 \u0437\u0430\u0432\u0442\u0440\u0430?', TRIAGE_OUT_OF_DOMAIN),
        ('sprav mi to', TRIAGE_UNCLEAR_NEEDS_CLARIFICATION),
        ('Treba report trzieb \u0431\u0443\u0434\u044c \u043b\u0430\u0441\u043a\u0430', TRIAGE_NEW_BUSINESS_FEATURE_REQUEST),
        ('em mozno poslat fakturu emailom', 'send_invoice_email'),
    ]

    for user_input, expected in examples:
        result = classify_info_help_triage(user_input_text=user_input)
        if expected in {'send_invoice_email', 'google_drive_invoice_storage', 'sms_reminders'}:
            assert result.capability_id == expected
            assert result.triage_class == 'known_product_capability'
        else:
            assert result.triage_class == expected


def test_info_help_service_has_no_runtime_side_effect_imports() -> None:
    source = inspect.getsource(info_help)

    forbidden_fragments = (
        'openai',
        'transcribe',
        'aiogram',
        'sqlite',
        'InvoiceService',
        'SupplierService',
        'ContactService',
        'FSInputFile',
        'open(',
    )
    for fragment in forbidden_fragments:
        assert fragment not in source
