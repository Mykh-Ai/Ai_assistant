import inspect

from bot.services import info_help
from bot.services.info_help import build_product_truth_guidance, classify_info_help_capability


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


def test_ambiguous_direct_invoice_text_is_not_info_help() -> None:
    assert classify_info_help_capability(user_input_text='Vytvor faktúru pre ABC za opravu 100 eur') is None


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
