from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any

from openai import AsyncOpenAI


_UNKNOWN = 'unknown'
_QUANTITY_UNIT_PRICE_CANONICAL = 'quantity_unit_price_pair'
_SUPPORTED_CONFIRM_LANGUAGES = ['sk', 'uk', 'ru']
logger = logging.getLogger(__name__)


def _tokenize(value: str) -> set[str]:
    tokens = {token for token in re.findall(r'[^\W\d_]+', value.lower(), flags=re.UNICODE) if token}
    normalized: set[str] = set()
    for token in tokens:
        norm = unicodedata.normalize('NFKD', token)
        normalized.add(''.join(ch for ch in norm if not unicodedata.combining(ch)))
    return normalized


def _matches_top_level_delete_invoice(tokens: set[str]) -> bool:
    delete_verbs = {
        'vymaz',
        'vymazat',
        'zmaz',
        'zmazat',
        'odstran',
        'odstranit',
        'delete',
        'remove',
        'vimas',
        'vima',
        'vimaz',
        '\u0432\u0438\u0434\u0430\u043b\u0438',
        '\u0432\u0438\u0434\u0430\u043b\u0438\u0442\u0438',
        '\u0443\u0434\u0430\u043b\u0438',
        '\u0443\u0434\u0430\u043b\u0438\u0442\u044c',
        '\u0432\u044b\u043c\u0430\u0436\u044c',
        '\u0432\u044b\u043c\u0430\u0437\u0430\u0442\u044c',
    }
    invoice_targets = {
        'fakturu',
        'faktura',
        'faktury',
        'invoice',
        '\u0444\u0430\u043a\u0442\u0443\u0440\u0443',
        '\u0444\u0430\u043a\u0442\u0443\u0440\u0430',
        '\u0444\u0430\u043a\u0442\u0443\u0440\u044b',
    }
    return bool(tokens.intersection(delete_verbs)) and bool(tokens.intersection(invoice_targets))


def _matches_top_level_show_invoice(tokens: set[str]) -> bool:
    show_verbs = {
        'ukaz',
        'zobraz',
        'otvor',
        'otvorit',
        'show',
        'open',
        '\u043f\u043e\u043a\u0430\u0436\u0438',
        '\u043f\u043e\u043a\u0430\u0437\u0430\u0442\u0438',
        '\u043e\u0442\u043a\u0440\u043e\u0439',
        '\u043e\u0442\u043a\u0440\u044b\u0442\u044c',
        '\u0432\u0456\u0434\u043a\u0440\u0438\u0439',
        '\u0432\u0456\u0434\u043a\u0440\u0438\u0442\u0438',
    }
    invoice_targets = {
        'fakturu',
        'faktura',
        'faktury',
        'invoice',
        '\u0444\u0430\u043a\u0442\u0443\u0440\u0443',
        '\u0444\u0430\u043a\u0442\u0443\u0440\u0430',
        '\u0444\u0430\u043a\u0442\u0443\u0440\u044b',
    }
    return bool(tokens.intersection(show_verbs)) and bool(tokens.intersection(invoice_targets))


_STT_ANO_ARTIFACTS = {
    'ah nao',
    'a nao',
    'ah no',
    'a no',
    '\u0430\u0445\u043d\u044f\u043e',
}


def _is_stt_ano_noise(normalized: str) -> bool:
    return normalized in _STT_ANO_ARTIFACTS


def _is_ambiguous_stt_yes_no_noise(normalized: str) -> bool:
    return normalized in {
        'ah nao',
        'a nao',
        'ah non',
        'a non',
        'ah no',
        'a no',
        'ah nu',
        'a nu',
        'ах ну',
        'ах ні',
        'ах не',
    }


def _fallback_for_context(context_name: str, text: str, allowed: set[str]) -> str:
    tokens = _tokenize(text)
    if context_name == 'invoice_edit_item_target_selection':
        numeric_match = re.search(r'\b(\d+)\b', text)
        if numeric_match:
            numeric_value = numeric_match.group(1)
            if numeric_value in allowed:
                return numeric_value
    if not tokens:
        return _UNKNOWN

    if context_name == 'top_level_action':
        normalized_text = _normalize_bounded_reply_text(text)
        start_phrases = {
            'zacat',
            'spustit',
            'start',
            'start bot',
            'spusti bot',
            '\u043f\u043e\u0447\u0430\u0442\u0438',
            '\u0437\u0430\u043f\u0443\u0441\u0442\u0438 \u0431\u043e\u0442\u0430',
            '\u043d\u0430\u0447\u0430\u0442\u044c',
        }
        show_supplier_profile_phrases = {
            'moj profil',
            'ukaz moj profil',
            'zobraz moj profil',
            'nastavit dodavatela',
            '\u043f\u043e\u043a\u0430\u0436\u0438 \u043c\u0456\u0439 \u043f\u0440\u043e\u0444\u0456\u043b\u044c',
            '\u043f\u043e\u043a\u0430\u0436\u0438 \u043c\u0456\u0438 \u043f\u0440\u043e\u0444\u0456\u043b\u044c',
            '\u043f\u043e\u043a\u0430\u0436\u0438 \u043c\u043e\u0439 \u043f\u0440\u043e\u0444\u0438\u043b\u044c',
            '\u043f\u043e\u043a\u0430\u0436\u0438 \u043c\u043e\u0438 \u043f\u0440\u043e\u0444\u0438\u043b\u044c',
        }
        edit_supplier_phrases = {
            'upravit moj profil',
            'zmenit moj profil',
            'upravit udaje firmy',
            'upravit dodavatela',
            'zmen moj profil',
            '\u0437\u043c\u0456\u043d\u0438 \u043c\u0456\u0439 \u043f\u0440\u043e\u0444\u0456\u043b\u044c',
            '\u0437\u043c\u0456\u043d\u0438 \u043c\u0456\u0438 \u043f\u0440\u043e\u0444\u0456\u043b\u044c',
            '\u0437\u043c\u0456\u043d\u0438\u0442\u0438 \u043c\u0456\u0439 \u043f\u0440\u043e\u0444\u0456\u043b\u044c',
            '\u0437\u043c\u0456\u043d\u0438\u0442\u0438 \u043c\u0456\u0438 \u043f\u0440\u043e\u0444\u0456\u043b\u044c',
        }
        show_recent_accounting_phrases = {
            'posledne blocky',
            'ukaz posledne blocky',
            'ukaz posledne doklady',
            'posledne doklady',
            '\u043f\u043e\u043a\u0430\u0436\u0438 \u043e\u0441\u0442\u0430\u043d\u043d\u0456 \u0447\u0435\u043a\u0438',
            '\u043e\u0441\u0442\u0430\u043d\u043d\u0456 \u0447\u0435\u043a\u0438',
        }
        add_receipt_verbs = {
            'pridaj',
            'dodaj',
            'dodat',
            'nahraj',
            'nahrat',
            'spracuj',
            'spracovat',
            '\u0434\u043e\u0434\u0430\u0439',
            '\u0434\u043e\u0434\u0430\u0438',
            '\u0434\u043e\u0434\u0430\u0442\u0438',
            '\u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436',
            '\u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0438\u0442\u0438',
            '\u0437\u0430\u0433\u0440\u0443\u0437\u0438',
            '\u0437\u0430\u0433\u0440\u0443\u0437\u0438\u0442\u044c',
        }
        receipt_targets = {
            'blocek',
            'blocky',
            'doklad',
            'doklady',
            'receipt',
            '\u0447\u0435\u043a',
            '\u0447\u0435\u043a\u0438',
            '\u0447\u0435\u043a\u0430',
        }
        incoming_invoice_targets = {'prijatu', 'prijata', 'incoming'}
        delete_database_phrases = {
            'vymazat databazu',
            'chcem vymazat moju databazu',
            'zmazat moje udaje',
            'zrusit moj ucet',
            '\u0432\u0438\u0434\u0430\u043b\u0438 \u043c\u043e\u044e \u0431\u0430\u0437\u0443',
            '\u0432\u0438\u0434\u0430\u043b\u0438\u0442\u0438 \u043c\u043e\u044e \u0431\u0430\u0437\u0443',
            '\u0443\u0434\u0430\u043b\u0438\u0442\u044c \u043c\u043e\u044e \u0431\u0430\u0437\u0443',
            '\u0445\u043e\u0447\u0443 \u0443\u0434\u0430\u043b\u0438\u0442\u044c \u043c\u043e\u044e \u0431\u0430\u0437\u0443',
        }
        delete_database_verbs = {
            'vymazat',
            'zmazat',
            'zrusit',
            'odstranit',
            'delete',
            'remove',
            '\u0432\u0438\u0434\u0430\u043b\u0438',
            '\u0432\u0438\u0434\u0430\u043b\u0438\u0442\u0438',
            '\u0443\u0434\u0430\u043b\u0438',
            '\u0443\u0434\u0430\u043b\u0438\u0442\u044c',
        }
        delete_database_targets = {
            'databazu',
            'database',
            'udaje',
            'ucet',
            '\u0431\u0430\u0437\u0443',
            '\u0434\u0430\u043d\u0456',
            '\u0434\u0430\u043d\u043d\u044b\u0435',
            '\u0430\u043a\u043a\u0430\u0443\u043d\u0442',
        }
        create_invoice_triggers = {
            'fakturu',
            'faktura',
            'faktury',
            'фактуру',
            'invoice',
            'vytvor',
            'sprav',
            'urob',
            'zrob',
            'сделай',
            'витворить',
            'створи',
        }
        add_contact_verbs = {
            'pridaj',
            'dodaj',
            'add',
            'uloz',
            'ulozit',
            'save',
            'додай',
            'добавь',
            'добавить',
        }
        add_contact_targets = {'kontakt', 'контакт', 'контрагента', 'firmu', 'company', 'spolocnost', 'контрагент'}
        add_service_alias_verbs = {
            'pridaj',
            'dodaj',
            'add',
            'создай',
            'додай',
            'добавь',
            'predaj',
            'предай',
        }
        add_service_alias_targets = {
            'sluzbu',
            'sluzba',
            'polozku',
            'polozka',
            'службу',
            'положку',
            'живность',
            'item',
            'service',
        }

        if 'start' in allowed and normalized_text in start_phrases:
            return 'start'
        if 'edit_supplier' in allowed and normalized_text in edit_supplier_phrases:
            return 'edit_supplier'
        if 'show_supplier_profile' in allowed and normalized_text in show_supplier_profile_phrases:
            return 'show_supplier_profile'
        if 'show_recent_accounting_documents' in allowed and normalized_text in show_recent_accounting_phrases:
            return 'show_recent_accounting_documents'
        if 'add_receipt' in allowed and tokens.intersection(add_receipt_verbs) and (
            tokens.intersection(receipt_targets)
            or (tokens.intersection(incoming_invoice_targets) and tokens.intersection({'fakturu', 'faktura', 'invoice'}))
        ):
            return 'add_receipt'
        if 'delete_user_database' in allowed and (
            normalized_text in delete_database_phrases
            or (tokens.intersection(delete_database_verbs) and tokens.intersection(delete_database_targets))
        ):
            return 'delete_user_database'
        if 'send_invoice' in allowed and tokens.intersection({'posli', 'send', 'відправ', 'отправь'}):
            return 'send_invoice'
        if 'edit_existing_invoice' in allowed and tokens.intersection({'upravit', 'редагувати', 'исправь', 'изменить', 'управить'}):
            return 'edit_existing_invoice'
        if 'delete_existing_invoice' in allowed and _matches_top_level_delete_invoice(tokens):
            return 'delete_existing_invoice'
        if 'show_existing_invoice' in allowed and _matches_top_level_show_invoice(tokens):
            return 'show_existing_invoice'
        if 'edit_invoice' in allowed and tokens.intersection({'upravit', 'редагувати', 'исправь', 'изменить'}):
            return 'edit_invoice'
        if 'create_invoice' in allowed and tokens.intersection(create_invoice_triggers):
            return 'create_invoice'
        if 'add_contact' in allowed and tokens.intersection(add_contact_verbs) and tokens.intersection(add_contact_targets):
            return 'add_contact'
        if 'add_service_alias' in allowed and tokens.intersection(add_service_alias_verbs) and tokens.intersection(
            add_service_alias_targets
        ):
            return 'add_service_alias'
        return _UNKNOWN

    if context_name == 'invoice_preview_confirmation':
        if 'schvalit' in allowed and tokens.intersection(
            {'schvalit', 'schvalit', 'potvrdit', 'potvrdzujem', 'approve', 'confirm', 'save', 'ano', 'tak', 'да', 'так'}
        ):
            return 'schvalit'
        if 'upravit' in allowed and tokens.intersection(
            {'upravit', 'edit', 'change', 'correct', 'opravit', 'исправить', 'изменить', 'редагувати'}
        ):
            return 'upravit'
        if 'zrusit' in allowed and tokens.intersection(
            {'zrusit', 'cancel', 'delete', 'discard', 'remove', 'nie', 'ní', 'ні', 'нет', 'íåò', 'nechcem', 'no'}
        ):
            return 'zrusit'
        if 'ano' in allowed and tokens.intersection(
            {'ano', 'tak', 'так', 'да', 'добре', 'ok', 'yes', 'potvrdzujem'}
        ):
            return 'ano'
        if 'nie' in allowed and tokens.intersection({'nie', 'ні', 'нет', 'cancel', 'nechcem', 'no'}):
            return 'nie'
        return _UNKNOWN

    if context_name == 'invoice_postpdf_decision':
        if 'schvalit' in allowed and tokens.intersection(
            {'schvalit', 'подтвердить', 'схвалити', 'approve', 'да', 'так', 'potvrdit'}
        ):
            return 'schvalit'
        if 'upravit' in allowed and tokens.intersection(
            {'upravit', 'редагувати', 'зміни', 'изменить', 'исправить', 'управить'}
        ):
            return 'upravit'
        if 'zrusit' in allowed and tokens.intersection(
            {
                'zrusit',
                'видалити',
                'удалить',
                'delete',
                'отменить',
                'скасувати',
                'знищити',
                'зрушити',
                'зрушить',
                'нет',
                'ні',
                'nie',
            }
        ):
            return 'zrusit'
        return _UNKNOWN

    if context_name == 'contact_confirm':
        if 'ano' in allowed and tokens.intersection({'ano', 'áno', 'tak', 'yes', 'да'}):
            return 'ano'
        if 'nie' in allowed and tokens.intersection({'nie', 'ні', 'нет', 'no', 'cancel'}):
            return 'nie'
        return _UNKNOWN

    if context_name == 'invoice_edit_scope_selection':
        if 'invoice_level' in allowed and tokens.intersection({'faktura', 'faktúra', 'invoice', 'cislo', 'číslo', 'datum', 'dátum'}):
            return 'invoice_level'
        if 'item_level' in allowed and tokens.intersection({'polozka', 'položka', 'sluzba', 'služba', 'opis', 'detail'}):
            return 'item_level'
        return _UNKNOWN

    if context_name == 'invoice_edit_invoice_action':
        if 'edit_invoice_number' in allowed and tokens.intersection({'cislo', 'číslo', 'number', 'num'}):
            return 'edit_invoice_number'
        if 'edit_invoice_issue_date' in allowed and tokens.intersection({'vystavenia', 'vystavenie', 'issue'}):
            return 'edit_invoice_issue_date'
        if 'edit_invoice_delivery_date' in allowed and tokens.intersection({'dodania', 'dodanie', 'delivery'}):
            return 'edit_invoice_delivery_date'
        if 'edit_invoice_due_date' in allowed and tokens.intersection({'splatnosti', 'splatnost', 'due'}):
            return 'edit_invoice_due_date'
        if 'edit_invoice_date' in allowed and tokens.intersection({'datum', 'dátum', 'date'}):
            return 'edit_invoice_date'
        return _UNKNOWN

    if context_name == 'invoice_edit_item_target_selection':
        ordered_candidates = [
            ('1', {'1', 'prva', 'prvá', 'prvy', 'prvý', 'jedna', 'jeden'}),
            ('2', {'2', 'druha', 'druhá', 'druhy', 'druhý', 'dva', 'dve'}),
            ('3', {'3', 'tretia', 'treti', 'tretí', 'tri'}),
        ]
        for canonical_index, hint_tokens in ordered_candidates:
            if canonical_index in allowed and tokens.intersection(hint_tokens):
                return canonical_index
        return _UNKNOWN

    if context_name == 'invoice_edit_item_action':
        if 'edit_item_quantity' in allowed and tokens.intersection({'mnozstvo', 'množstvo', 'quantity', 'qty'}):
            return 'edit_item_quantity'
        if 'edit_item_unit_price' in allowed and tokens.intersection(
            {'cena', 'cenu', 'ціна', 'unit', 'price', 'mj', 'm.j', 'jednotku', 'jednotka', 'odinicu', 'одиницю'}
        ):
            return 'edit_item_unit_price'
        if 'edit_item_total_amount' in allowed and tokens.intersection({'suma', 'sumu', 'spolu', 'total', 'amount'}):
            return 'edit_item_total_amount'
        if 'clear_item_details' in allowed and tokens.intersection(
            {'vymazat', 'vymazať', 'zmazat', 'zmazať', 'odstranit', 'odstrániť', 'clear', 'delete'}
        ) and tokens.intersection({'detail', 'detaily', 'details', 'poznamka', 'poznámka'}):
            return 'clear_item_details'
        if 'add_item_details' in allowed and tokens.intersection(
            {'pridat', 'pridať', 'doplnit', 'doplniť', 'add'}
        ) and tokens.intersection({'detail', 'detaily', 'details', 'poznamka', 'poznámka'}):
            return 'add_item_details'
        if 'replace_main_description' in allowed and tokens.intersection(
            {'novy', 'nový', 'opis', 'popis', 'description'}
        ):
            return 'replace_main_description'
        if 'replace_service' in allowed and tokens.intersection(
            {'sluzba', 'služba', 'sluzbu', 'službu', 'service', 'polozka', 'položka', 'polozku', 'položku'}
        ):
            return 'replace_service'
        if 'add_item_details' in allowed and tokens.intersection({'detail', 'detaily', 'details', 'poznamka', 'poznámka'}):
            return 'add_item_details'
        return _UNKNOWN

    return _UNKNOWN


def _normalize_bounded_reply_text(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r'[^\w\s\u0400-\u04FF-]', ' ', cleaned, flags=re.UNICODE)
    cleaned = ' '.join(cleaned.split())
    if not cleaned:
        return ''
    normalized = unicodedata.normalize('NFKD', cleaned)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


_NEGATION_MARKERS = {'ne', 'nie', 'not', 'no', 'не', 'ні', 'нет', 'нічого', 'ничего', 'nechcem'}


def _contains_decision_marker(
    normalized: str,
    *,
    exact_values: set[str],
    prefixes: tuple[str, ...] = (),
    ignore_negated: bool = False,
) -> bool:
    tokens = normalized.split()
    for index, token in enumerate(tokens):
        if token not in exact_values and not (prefixes and token.startswith(prefixes)):
            continue
        if ignore_negated and any(
            previous in _NEGATION_MARKERS for previous in tokens[max(0, index - 3) : index]
        ):
            continue
        return True
    return False


def _resolve_local_decision_markers(
    *,
    normalized: str,
    allowed_outputs: set[str],
    approve_values: set[str],
    edit_values: set[str],
    cancel_values: set[str],
) -> str:
    matched: set[str] = set()
    if 'schvalit' in allowed_outputs and _contains_decision_marker(
        normalized,
        exact_values=approve_values,
        prefixes=('зберег', 'збереж', 'зберіг', 'сохран'),
    ):
        matched.add('schvalit')
    if 'upravit' in allowed_outputs and _contains_decision_marker(
        normalized,
        exact_values=edit_values,
        prefixes=('uprav', 'oprav', 'редаг', 'відредаг', 'исправ'),
        ignore_negated=True,
    ):
        matched.add('upravit')
    if 'zrusit' in allowed_outputs and _contains_decision_marker(
        normalized,
        exact_values=cancel_values,
    ):
        matched.add('zrusit')

    if len(matched) == 1:
        return next(iter(matched))
    return _UNKNOWN


def _fallback_yes_no_confirmation(*, context_name: str, normalized: str, allowed_outputs: set[str]) -> str:
    if _is_stt_ano_noise(normalized) and 'ano' in allowed_outputs:
        return 'ano'
    if context_name == 'invoice_customer_alias_confirm' and _is_ambiguous_stt_yes_no_noise(normalized):
        return _UNKNOWN
    positive = {'ano', 'tak', 'ok', 'da', 'yes', 'так', 'да'}
    negative = {'nie', 'net', 'no', 'ні', 'нет'}
    if normalized in positive and 'ano' in allowed_outputs:
        return 'ano'
    if normalized in negative and 'nie' in allowed_outputs:
        return 'nie'
    return _UNKNOWN


def _fallback_bounded_confirmation_reply(
    *,
    context_name: str,
    expected_reply_type: str,
    text: str,
    allowed_outputs: set[str],
) -> str:
    normalized = _normalize_bounded_reply_text(text)
    if not normalized:
        return _UNKNOWN

    if expected_reply_type == 'yes_no_confirmation':
        return _fallback_yes_no_confirmation(
            context_name=context_name,
            normalized=normalized,
            allowed_outputs=allowed_outputs,
        )

    if expected_reply_type == 'global_cancel':
        cancel_values = {
            'cancel',
            'zrusit',
            'zrusit',
            'skoncit',
            'spat',
            'naspat',
            '\u043d\u0430\u0437\u0430\u0434',
            '\u0441\u043a\u0430\u0441\u0443\u0432\u0430\u0442\u0438',
            '\u0432\u0456\u0434\u043c\u0456\u043d\u0438\u0442\u0438',
            '\u0432\u0456\u0434\u043c\u0438\u043d\u0438\u0442\u0438',
            '\u043e\u0442\u043c\u0435\u043d\u0438\u0442\u044c',
            '\u043f\u043e\u0447\u043d\u0438 \u0437 \u043f\u043e\u0447\u0430\u0442\u043a\u0443',
            '\u043f\u043e\u0447\u0430\u0442\u0438 \u0437 \u043f\u043e\u0447\u0430\u0442\u043a\u0443',
            '\u043d\u0430\u0447\u0430\u0442\u044c \u0441\u043d\u0430\u0447\u0430\u043b\u0430',
        }
        if 'cancel' in allowed_outputs and normalized in cancel_values:
            return 'cancel'
        return _UNKNOWN

    if (
        context_name in {'invoice_preview_confirmation', 'invoice_postpdf_decision'}
        and _is_stt_ano_noise(normalized)
        and expected_reply_type in {'draft_review_decision', 'postpdf_decision'}
    ):
        if 'schvalit' in allowed_outputs:
            return 'schvalit'

    if context_name == 'idle_attachment_route_choice' and expected_reply_type == 'attachment_route_choice':
        tokens = set(normalized.split())
        matched: set[str] = set()
        if tokens.intersection({'kontakt', 'contact', 'kontrahent', 'firmu', 'spolocnost'}) and tokens.intersection(
            {'vytvorit', 'vytvor', 'pridat', 'pridaj', 'create', 'add'}
        ):
            matched.add('create_contact')
        if tokens.intersection({'zmluvu', 'zmluva', 'contract'}) and tokens.intersection(
            {'ulozit', 'uloz', 'save', 'archivovat'}
        ):
            matched.add('save_contract')
        if tokens.intersection({'zrusit', 'zrus', 'cancel', 'stop'}):
            matched.add('cancel')
        if normalized in {'nie', 'no', 'cancel'}:
            matched.add('cancel')
        return next(iter(matched)) if len(matched) == 1 else _UNKNOWN

    if context_name == 'idle_attachment_document_type_choice' and expected_reply_type == 'attachment_document_type_choice':
        tokens = set(normalized.split())
        matched: set[str] = set()
        if tokens.intersection({'blocek', 'block', 'receipt', 'uctenka'}):
            matched.add('receipt')
        if tokens.intersection({'faktura', 'fakturu', 'invoice'}) and tokens.intersection(
            {'prijata', 'prijatu', 'incoming', 'dodavatelska'}
        ):
            matched.add('incoming_invoice')
        if tokens.intersection({'zmluva', 'zmluvu', 'contract'}):
            matched.add('contract')
        if tokens.intersection({'kontakt', 'contact', 'kontrahent', 'firmu', 'spolocnost'}):
            matched.add('contact_source')
        if tokens.intersection({'zrusit', 'zrus', 'cancel', 'stop'}):
            matched.add('cancel')
        return next(iter(matched)) if len(matched) == 1 else _UNKNOWN

    if (
        context_name in {'invoice_preview_confirmation', 'invoice_postpdf_decision', 'accounting_document_intake_preview'}
        and expected_reply_type in {'draft_review_decision', 'postpdf_decision'}
    ):
        approve_values = {
            'schvalit',
            'potvrdit',
            'potvrd',
            'potvrdzujem',
            'approve',
            'confirm',
            'save',
            'zachovat',
            'zachovajte',
            'ano',
            'tak',
            'ok',
            'da',
            'uloz',
            'ulozit',
            'ulozte',
            'ulozim',
            'ulozime',
            'да',
            'так',
            'схвалити',
            'схвалить',
            'подтвердить',
            'підтвердити',
        }
        edit_values = {
            'upravit',
            'upravte',
            'opravit',
            'opravte',
            'zmenit',
            'edit',
            'change',
            'correct',
            'изменить',
            'исправить',
            'редагувати',
            'відредагувати',
            'відредагуй',
            'змінити',
            'змініть',
            'поміняй',
            'управить',
        }
        if context_name in {'invoice_preview_confirmation', 'accounting_document_intake_preview'}:
            cancel_values = {
                'zrusit',
                'cancel',
                'delete',
                'discard',
                'remove',
                'zahodit',
                'отменить',
                'скасувати',
                'нет',
                'ні',
                'nie',
                'no',
                'зрушити',
                'зрушить',
                'видалити',
                'удалить',
            }
        else:
            cancel_values = {
                'zrusit',
                'cancel',
                'zahodit',
                'отменить',
                'скасувати',
                'нет',
                'ні',
                'nie',
                'no',
                'зрушити',
                'зрушить',
                'видалити',
                'удалить',
            }

        return _resolve_local_decision_markers(
            normalized=normalized,
            allowed_outputs=allowed_outputs,
            approve_values=approve_values,
            edit_values=edit_values,
            cancel_values=cancel_values,
        )

    return _UNKNOWN


_NUMBER_WORDS_TO_FLOAT = {
    'jeden': 1.0,
    'jedna': 1.0,
    'jedno': 1.0,
    'raz': 1.0,
    'один': 1.0,
    'одна': 1.0,
    'одно': 1.0,
    'два': 2.0,
    'две': 2.0,
    'дві': 2.0,
    'dva': 2.0,
    'dve': 2.0,
    'tri': 3.0,
    'три': 3.0,
    'styri': 4.0,
    'štyri': 4.0,
    'четыре': 4.0,
    'чотири': 4.0,
}

_QTY_TOKEN_PATTERN = (
    r'\d+(?:[.,]\d+)?|'
    r'jeden|jedna|jedno|raz|dva|dve|tri|styri|štyri|'
    r'один|одна|одно|два|две|дві|три|четыре|чотири'
)
_PRICE_NUMBER_PATTERN = r'\d+(?:[.,]\d+)?'
_PAIR_SPACED_PATTERN = re.compile(
    rf'^\s*(?P<qty>{_QTY_TOKEN_PATTERN})\s+(?P<unit>{_PRICE_NUMBER_PATTERN})\s*$',
    flags=re.IGNORECASE,
)
_PAIR_MULTIPLIER_PATTERN = re.compile(
    rf'^\s*(?P<qty>{_QTY_TOKEN_PATTERN})\s*(?:\*|x|kr[aá]t|крат|razi|razy|раз|раза|рази|kusy|kus|ks)?\s*(?:po|по)?\s*(?P<unit>{_PRICE_NUMBER_PATTERN})\s*$',
    flags=re.IGNORECASE,
)
_PAIR_LABELED_PATTERN = re.compile(
    rf'^\s*(?:mno[zž]stvo|koli[cč]estvo|количество)\s*(?P<qty>{_QTY_TOKEN_PATTERN})\s*[,;]?\s*(?:cena(?:\s+za\s+(?:kus|ks|jednotku))?|цена(?:\s+за\s+(?:штуку|единицу|ед))?)\s*(?P<unit>{_PRICE_NUMBER_PATTERN})\s*$',
    flags=re.IGNORECASE,
)
_SINGLE_PRICE_PATTERN = re.compile(r'^\s*(?P<unit>\d+(?:[.,]\d+)?)\s*$')


def _parse_positive_float(value: str) -> float | None:
    try:
        parsed = float(value.replace(',', '.').strip())
    except ValueError:
        return None
    if parsed <= 0:
        return None
    return parsed


def _parse_quantity_token(value: str) -> float | None:
    parsed = _parse_positive_float(value)
    if parsed is not None:
        return parsed
    return _NUMBER_WORDS_TO_FLOAT.get(value.strip().lower())


def _fallback_quantity_unit_price_pair(text: str) -> tuple[float, float] | None:
    normalized_text = text.strip()
    if not normalized_text:
        return None

    for pattern in (_PAIR_SPACED_PATTERN, _PAIR_MULTIPLIER_PATTERN, _PAIR_LABELED_PATTERN):
        match = pattern.match(normalized_text)
        if not match:
            continue
        quantity = _parse_quantity_token(match.group('qty'))
        unit_price = _parse_positive_float(match.group('unit'))
        if quantity is not None and unit_price is not None:
            return quantity, unit_price

    single_match = _SINGLE_PRICE_PATTERN.match(normalized_text)
    if single_match:
        unit_price = _parse_positive_float(single_match.group('unit'))
        if unit_price is not None:
            return 1.0, unit_price

    return None


async def resolve_semantic_action(
    *,
    context_name: str,
    allowed_actions: list[str],
    user_input_text: str,
    api_key: str | None,
    model: str,
    auxiliary_context: dict[str, Any] | None = None,
    action_hints: dict[str, Any] | None = None,
) -> str:
    allowed = {value.strip() for value in allowed_actions if value and value.strip()}
    if _UNKNOWN not in allowed:
        allowed.add(_UNKNOWN)

    cleaned = user_input_text.strip()
    if not cleaned:
        return _UNKNOWN

    local_priority = _fallback_for_context(context_name, cleaned, allowed)
    if context_name == 'top_level_action' and local_priority in {
        'start',
        'show_supplier_profile',
        'show_existing_invoice',
        'edit_supplier',
        'show_recent_accounting_documents',
        'delete_user_database',
        'edit_existing_invoice',
        'delete_existing_invoice',
    }:
        return local_priority

    if api_key and api_key.startswith('sk-'):
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a bounded semantic canonicalizer. '
                            'Return JSON only: {"canonical_action":"..."} where value is one allowed action or "unknown". '
                            'Never return explanations. '
                            'User input may be Slovak, Ukrainian, Russian, mixed-language, colloquial, or STT-noisy. '
                            'First infer the user meaning and internally normalize it to Slovak FakturaBot product semantics. '
                            'Then choose exactly one allowed canonical action or "unknown". '
                            'Do not require literal command, alias, or example matching. '
                            'Action hints describe product meaning; any examples are illustrative only and never a whitelist. '
                            'Return "unknown" only when the normalized meaning is genuinely unclear or no allowed action fits.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': context_name,
                                'current_state': auxiliary_context.get('current_state') if isinstance(auxiliary_context, dict) else None,
                                'supported_languages': _SUPPORTED_CONFIRM_LANGUAGES,
                                'allowed_actions': sorted(allowed),
                                'user_input_text': cleaned,
                                'expected_output': {'canonical_action': 'one allowed token or unknown'},
                                'auxiliary_context': auxiliary_context or {},
                                'action_hints': action_hints or {},
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            parsed = json.loads(raw)
            canonical = str(parsed.get('canonical_action', _UNKNOWN)).strip()
            if canonical in allowed:
                return canonical
        except Exception:
            pass

    return local_priority


async def resolve_semantic_value(
    *,
    context_name: str,
    allowed_values: list[str],
    user_input_text: str,
    api_key: str | None,
    model: str,
    auxiliary_context: dict[str, Any] | None = None,
) -> str:
    return await resolve_semantic_action(
        context_name=context_name,
        allowed_actions=allowed_values,
        user_input_text=user_input_text,
        api_key=api_key,
        model=model,
        auxiliary_context=auxiliary_context,
    )


async def resolve_invoice_date_normalization(
    *,
    date_field: str,
    user_input_text: str,
    api_key: str | None,
    model: str,
    invoice_context: dict[str, Any] | None = None,
) -> str:
    cleaned = user_input_text.strip()
    if not cleaned:
        return _UNKNOWN

    if api_key and api_key.startswith('sk-'):
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a bounded normalization engine for invoice date editing. '
                            'Return strict JSON only in format {"normalized_date":"DD.MM.RRRR"} or {"normalized_date":"unknown"}. '
                            'Do not return explanations or extra keys.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': 'invoice_edit_date_value',
                                'date_field': date_field,
                                'required_format': 'DD.MM.RRRR',
                                'allowed_output': ['DD.MM.RRRR', 'unknown'],
                                'normalization_contract': {
                                    'mode': 'bounded_value_normalization',
                                    'do_not_explain': True,
                                    'do_not_return_free_text': True,
                                    'unknown_only_for': ['truly_ambiguous', 'missing_date', 'stt_noise'],
                                },
                                'user_input_text': cleaned,
                                'invoice_context': invoice_context or {},
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            parsed = json.loads(raw)
            normalized = str(parsed.get('normalized_date', _UNKNOWN)).strip()
            if normalized == _UNKNOWN:
                return _UNKNOWN
            if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', normalized):
                return normalized
            return _UNKNOWN
        except Exception:
            logger.exception('Invoice date normalization failed')

    if re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', cleaned):
        return cleaned
    return _UNKNOWN


async def resolve_bounded_confirmation_reply(
    *,
    context_name: str,
    expected_reply_type: str,
    allowed_outputs: list[str],
    user_input_text: str,
    api_key: str | None,
    model: str,
    diagnostics: dict[str, Any] | None = None,
) -> str:
    allowed = {value.strip() for value in allowed_outputs if value and value.strip()}
    if _UNKNOWN not in allowed:
        allowed.add(_UNKNOWN)

    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update(
            {
                'raw_model_output': None,
                'normalized_output': _UNKNOWN,
                'fallback_used': False,
                'fallback_output': None,
            }
        )

    cleaned = user_input_text.strip()
    if not cleaned:
        if diagnostics is not None:
            diagnostics['fallback_used'] = True
            diagnostics['fallback_output'] = _UNKNOWN
        return _UNKNOWN

    local_output = _UNKNOWN
    if expected_reply_type == 'yes_no_confirmation':
        local_output = _fallback_bounded_confirmation_reply(
            context_name=context_name,
            expected_reply_type=expected_reply_type,
            text=cleaned,
            allowed_outputs=allowed,
        )
    if (
        context_name in {'invoice_preview_confirmation', 'invoice_postpdf_decision', 'accounting_document_intake_preview'}
        and expected_reply_type in {'draft_review_decision', 'postpdf_decision'}
    ):
        local_output = _fallback_bounded_confirmation_reply(
            context_name=context_name,
            expected_reply_type=expected_reply_type,
            text=cleaned,
            allowed_outputs=allowed,
        )

    normalized_cleaned = _normalize_bounded_reply_text(cleaned)
    if (
        context_name == 'invoice_customer_alias_confirm'
        and expected_reply_type == 'yes_no_confirmation'
        and _is_ambiguous_stt_yes_no_noise(normalized_cleaned)
        and not _is_stt_ano_noise(normalized_cleaned)
    ):
        if diagnostics is not None:
            diagnostics['fallback_used'] = True
            diagnostics['fallback_output'] = _UNKNOWN
            diagnostics['normalized_output'] = _UNKNOWN
        return _UNKNOWN

    if local_output != _UNKNOWN:
        if diagnostics is not None:
            diagnostics['fallback_used'] = True
            diagnostics['fallback_output'] = local_output
            diagnostics['normalized_output'] = local_output
        return local_output

    if api_key and api_key.startswith('sk-'):
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a bounded intent normalizer for short in-action confirmations/decisions. '
                            'Return JSON only in format {"canonical":"..."} where value is one allowed output token or "unknown". '
                            'Do not return any explanations. '
                            'Reasoning policy: '
                            'Step 1) infer user intent semantically (not literal matching) even if wording is short, multilingual, colloquial, or mildly STT-noisy. '
                            'Step 2) normalize that intent to the allowed canonical token for the current context. '
                            'Step 3) return "unknown" only when intent is truly ambiguous, not a confirmation/decision reply, or genuine STT garbage. '
                            'For expected_reply_type=yes_no_confirmation: user is NOT required to say exact "ano"/"nie"; '
                            'map clear affirmative intent across languages/forms to affirmative canonical output and clear negative intent to negative canonical output. '
                            'For expected_reply_type=draft_review_decision or postpdf_decision: '
                            'map clear approve/confirm/save-draft intent to schvalit, clear edit/change/correct intent to upravit, '
                            'and clear delete/cancel/remove/discard invoice-draft intent to zrusit, including multilingual/noisy variants. '
                            'For expected_reply_type=attachment_route_choice: map only clear route choice to create_contact, '
                            'save_contract, cancel, or unknown. '
                            'For expected_reply_type=attachment_document_type_choice: map only clear document-type clarification to '
                            'receipt, incoming_invoice, contract, contact_source, cancel, or unknown. '
                            'Phrases meaning "save changes" are approve/save intent, not edit intent; do not treat "changes" alone as an edit command. '
                            'Safety rule: do not guess destructive action when intent is unclear; use "unknown" for uncertainty.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': context_name,
                                'expected_reply_type': expected_reply_type,
                                'supported_input_languages': _SUPPORTED_CONFIRM_LANGUAGES,
                                'allowed_canonical_outputs': sorted(allowed),
                                'user_input_text': cleaned,
                                'normalization_contract': {
                                    'mode': 'semantic_intent_first',
                                    'unknown_only_for': [
                                        'true_ambiguity',
                                        'not_a_confirmation_or_decision_reply',
                                        'stt_garbage_or_nonsense',
                                    ],
                                    'context_rules': {
                                        'yes_no_confirmation': {
                                            'affirmative_intent': 'normalize_to_affirmative_token_in_allowed_outputs',
                                            'negative_intent': 'normalize_to_negative_token_in_allowed_outputs',
                                        },
                                        'postpdf_decision': {
                                            'approve_confirm_save_invoice_draft': 'schvalit_if_allowed',
                                            'edit_change_correct_invoice_draft': 'upravit_if_allowed',
                                            'delete_cancel_remove_discard_invoice_draft': 'zrusit_if_allowed',
                                        },
                                        'draft_review_decision': {
                                            'approve_confirm_save_invoice_draft': 'schvalit_if_allowed',
                                            'edit_change_correct_invoice_draft': 'upravit_if_allowed',
                                            'delete_cancel_remove_discard_invoice_draft': 'zrusit_if_allowed',
                                        },
                                    },
                                },
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            if diagnostics is not None:
                diagnostics['raw_model_output'] = raw
            parsed = json.loads(raw)
            canonical = str(parsed.get('canonical', _UNKNOWN)).strip()
            if canonical in allowed:
                if diagnostics is not None:
                    diagnostics['normalized_output'] = canonical
                return canonical
        except Exception:
            logger.exception('Bounded confirmation resolver failed; using fallback')

    fallback_output = _fallback_bounded_confirmation_reply(
        context_name=context_name,
        expected_reply_type=expected_reply_type,
        text=cleaned,
        allowed_outputs=allowed,
    )
    if diagnostics is not None:
        diagnostics['fallback_used'] = True
        diagnostics['fallback_output'] = fallback_output
        diagnostics['normalized_output'] = fallback_output
    return fallback_output


async def resolve_quantity_unit_price_pair(
    *,
    user_input_text: str,
    api_key: str | None,
    model: str,
    clarification_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cleaned = user_input_text.strip()
    if not cleaned:
        return {'canonical': _UNKNOWN}

    if api_key and api_key.startswith('sk-'):
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={'type': 'json_object'},
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a bounded semantic canonicalizer for invoice slot clarification. '
                            'Supported input languages: uk, ru, sk. '
                            'You parse only quantity and unit_price replies. '
                            'Valid inputs are either quantity+unit_price or unit_price-only; '
                            'for unit_price-only set quantity=1. '
                            'Return strict JSON only in one of two shapes: '
                            '{"canonical":"quantity_unit_price_pair","quantity":<number>,"unit_price":<number>} '
                            'or {"canonical":"unknown"}.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'context_name': 'invoice_slot_clarification',
                                'expected_reply_type': 'quantity_times_unit_price',
                                'supported_input_languages': ['uk', 'ru', 'sk'],
                                'clarification_context': clarification_context or {},
                                'user_input_text': cleaned,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            raw = response.choices[0].message.content or '{}'
            parsed = json.loads(raw)
            canonical = str(parsed.get('canonical', _UNKNOWN)).strip()
            if canonical == _QUANTITY_UNIT_PRICE_CANONICAL:
                quantity = _parse_positive_float(str(parsed.get('quantity', '')))
                unit_price = _parse_positive_float(str(parsed.get('unit_price', '')))
                if quantity is not None and unit_price is not None:
                    return {
                        'canonical': _QUANTITY_UNIT_PRICE_CANONICAL,
                        'quantity': quantity,
                        'unit_price': unit_price,
                    }
            if canonical == _UNKNOWN:
                return {'canonical': _UNKNOWN}
        except Exception:
            pass

    fallback = _fallback_quantity_unit_price_pair(cleaned)
    if fallback is None:
        return {'canonical': _UNKNOWN}

    quantity, unit_price = fallback
    return {
        'canonical': _QUANTITY_UNIT_PRICE_CANONICAL,
        'quantity': quantity,
        'unit_price': unit_price,
    }
