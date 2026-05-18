import inspect

from bot.services import info_help
from bot.services.info_help import (
    TRIAGE_ADMIN_REVIEW_CANDIDATE,
    TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
    TRIAGE_OUT_OF_DOMAIN,
    TRIAGE_SMALLTALK,
    TRIAGE_SPAM_OR_ABUSE,
    TRIAGE_UNCLEAR_NEEDS_CLARIFICATION,
    build_info_help_triage_guidance,
    build_product_truth_guidance,
    classify_info_help_capability,
    classify_info_help_triage,
    parse_info_help_triage_model_output,
)


def test_email_capability_question_renders_unsupported_product_truth_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='Vieš poslať faktúru emailom?')

    assert answer is not None
    assert 'Odosielanie faktúr emailom' in answer
    assert 'nepodporované' in answer
    assert 'externé prístupy' in answer
    assert 'I emailed the invoice.' not in answer


def test_google_drive_question_renders_external_limitation() -> None:
    answer = build_product_truth_guidance(user_input_text='Vie bot ukladať faktúry na Google Drive?')

    assert answer is not None
    assert 'Ukladanie faktúr na Google Drive' in answer
    assert 'nepodporované' in answer
    assert 'externé prístupy' in answer


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
    assert 'nevytvorím uloženú požiadavku' in answer
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


def test_add_receipt_how_to_renders_partial_guidance() -> None:
    answer = build_product_truth_guidance(user_input_text='Ako pridám bloček?')

    assert answer is not None
    assert 'Pridanie bločku alebo prijatej faktúry' in answer
    assert 'čiastočné' in answer
    assert 'fotka alebo PDF' in answer


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
    assert 'nevytvorím uloženú požiadavku' in answer


def test_custom_function_smoke_phrase_renders_product_truth_guidance() -> None:
    assert classify_info_help_capability(user_input_text='Chcem vlastnú funkciu') == 'customization_requests'
    answer = build_product_truth_guidance(user_input_text='Chcem vlastnú funkciu')

    assert answer is not None
    assert 'Požiadavky na úpravu' in answer
    assert 'nepodporované' in answer
    assert 'nevytvorím uloženú požiadavku' not in answer
    assert 'požiadavku vytvoril alebo uložil' in answer


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


def test_triage_model_output_rejects_free_form_answer_only() -> None:
    result = parse_info_help_triage_model_output('{"answer_text":"Sure, I can do that."}')

    assert result == info_help.InfoHelpTriageResult()


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
    assert 'ni\u010d neulo\u017eil ani neposlal' in answer


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
    assert 'Ni\u010d som neposlal ani neulo\u017eil' in answer


def test_multilingual_and_noisy_triage_examples() -> None:
    assert classify_info_help_triage(user_input_text='Vies poslat fakturu emailom?').capability_id == 'send_invoice_email'
    assert classify_info_help_triage(user_input_text='\u0427\u0438 \u043c\u043e\u0436\u043d\u0430 \u0437\u0431\u0435\u0440\u0456\u0433\u0430\u0442\u0438 \u0444\u0430\u043a\u0442\u0443\u0440\u0438 \u043d\u0430 Google Drive?').capability_id == 'google_drive_invoice_storage'
    assert classify_info_help_triage(user_input_text='\u041c\u043e\u0436\u043d\u043e \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0442\u044c SMS \u043d\u0430\u043f\u043e\u043c\u0438\u043d\u0430\u043d\u0438\u044f?').capability_id == 'sms_reminders'
    assert (
        classify_info_help_triage(user_input_text='Treba mesacny report trzieb, no tak trochu').triage_class
        == TRIAGE_NEW_BUSINESS_FEATURE_REQUEST
    )


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
