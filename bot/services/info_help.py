from __future__ import annotations

import re
import unicodedata
from typing import Any, Mapping

from bot.services.product_truth import get_safe_answer_payload, list_capabilities


_PRODUCT_TRUTH_OVERVIEW_IDS = (
    'create_invoice',
    'show_existing_invoice',
    'edit_existing_invoice',
    'delete_existing_invoice',
    'invoice_pdf_generation',
    'add_receipt_or_incoming_invoice',
    'show_recent_accounting_documents',
    'voice_invoice_intake',
    'send_invoice_email',
    'google_drive_invoice_storage',
    'sms_reminders',
    'accounting_export',
    'invoice_pdf_custom_template',
    'delete_user_database',
)

_RESERVED_INTENT_CAPABILITIES = {
    'send_invoice': 'send_invoice_email',
}

_STATUS_LABELS = {
    'supported': 'podporované',
    'partial': 'čiastočné',
    'planned': 'plánované',
    'unsupported': 'nepodporované',
    'unknown': 'neznáme',
}

_ACCOUNT_STATUS_LABELS = {
    'ready': 'pripravené',
    'requires_setup': 'vyžaduje nastavenie účtu',
    'requires_admin': 'vyžaduje správcu',
    'requires_external_credentials': 'vyžaduje externé prístupy',
    'unknown': 'neznáme',
}
_SLOVAK_CAPABILITY_COPY = {
    'create_invoice': {
        'title': 'Vytvorenie faktúry',
        'summary': 'Vytvorenie odosielanej faktúry je podporované cez existujúci fakturačný tok.',
        'limitation': 'Bežné použitie vyžaduje autorizovaného používateľa, profil dodávateľa, službu a kontakt.',
        'safe_next': 'Ak chcete faktúru naozaj vytvoriť, napíšte konkrétne údaje faktúry alebo použite /invoice.',
    },
    'send_invoice_email': {
        'title': 'Odosielanie faktúr emailom',
        'summary': 'Reálne odosielanie faktúr emailom nie je v aktuálnej verzii implementované.',
        'limitation': 'Emailové údaje môžu existovať v kontaktoch, ale neexistuje podporovaný odosielací tok.',
        'safe_next': 'Faktúru si môžete zobraziť alebo stiahnuť cez existujúce Telegram toky, kde sú dostupné.',
    },
    'google_drive_invoice_storage': {
        'title': 'Ukladanie faktúr na Google Drive',
        'summary': 'Ukladanie alebo synchronizácia faktúr na Google Drive nie je v aktuálnej verzii implementovaná.',
        'limitation': 'Faktúry sa ukladajú v systéme bota a dostupné sú cez existujúce Telegram postupy.',
        'safe_next': 'Google Drive by vyžadoval samostatnú integráciu, prístupy a schválený rozsah.',
    },
    'sms_reminders': {
        'title': 'SMS pripomienky',
        'summary': 'SMS pripomienky nie sú v aktuálnej verzii implementované.',
        'limitation': 'Nie je implementovaný SMS poskytovateľ, súhlasy, telefónne čísla ani plánovanie odosielania.',
        'safe_next': 'SMS by vyžadovali poskytovateľa, pravidlá súhlasu, cenu a samostatné testy.',
    },
    'accounting_export': {
        'title': 'Export do účtovníctva',
        'summary': 'Export do účtovného softvéru nie je v aktuálnej verzii implementovaný.',
        'limitation': 'Aktuálne účtovné dokumenty pokrývajú iba potvrdený príjem dokladov a nedávny prehľad tam, kde je podporený.',
        'safe_next': 'Export by potreboval cieľový softvér, formát alebo API, prístupy a samostatné schválenie.',
    },
    'invoice_pdf_custom_template': {
        'title': 'Vlastná PDF šablóna faktúry',
        'summary': 'Vlastná alebo stará PDF šablóna nie je v aktuálnej verzii dostupná.',
        'limitation': 'Faktúry sa generujú podľa zabudovaného rozloženia FakturaBotu.',
        'safe_next': 'Na vlastnú šablónu by bola potrebná samostatná úprava a kontrola PDF rozloženia.',
    },
    'customization_requests': {
        'title': 'Požiadavky na úpravu',
        'summary': 'Ukladanie požiadaviek na úpravu z Telegram bota zatiaľ nie je implementované.',
        'limitation': 'Bot nesmie tvrdiť, že požiadavku vytvoril alebo uložil.',
        'safe_next': 'Zatiaľ môžem iba pravdivo pomenovať, že ide o budúcu alebo samostatnú úpravu.',
    },
    'code_agent_handoff': {
        'title': 'Odovzdanie úlohy kódovaciemu agentovi',
        'summary': 'Odovzdanie úlohy kódovaciemu agentovi z Telegram bota nie je implementované.',
        'limitation': 'Implementačné úlohy stále vyžadujú ľudskú kontrolu a nie sú vytvárané Telegram botom.',
        'safe_next': 'Bot nesmie sľúbiť patch, merge, deploy ani odovzdanie agentovi.',
    },
    'add_receipt_or_incoming_invoice': {
        'title': 'Pridanie bločku alebo prijatej faktúry',
        'summary': 'Príjem bločku alebo prijatej faktúry je podporovaný čiastočne cez existujúci upload tok.',
        'limitation': 'Vyžaduje sa fotka alebo PDF; úprava a širšie typy dokumentov nie sú súčasťou tohto toku.',
        'safe_next': 'Použite /add_blocek alebo požiadajte o pridanie bločku a potom nahrajte fotku alebo PDF.',
    },
    'voice_invoice_intake': {
        'title': 'Hlasové zadanie faktúry',
        'summary': 'Hlas vie spustiť fakturačný tok a niektoré voľby, ale presné hodnoty zostávajú textové.',
        'limitation': 'IBAN, IČO, DIČ, email, čísla faktúr, sumy a presné popisy patria do textu alebo súboru.',
        'safe_next': 'Hlas používajte na zámer a bežné ovládanie; presné hodnoty zadajte textom.',
    },
    'delete_user_database': {
        'title': 'Vymazanie používateľskej databázy',
        'summary': 'Vymazanie používateľských dát je podporované len cez bezpečnostný tok s presným potvrdením.',
        'limitation': 'Hlas môže spustiť varovanie, ale finálne vymazanie vyžaduje presnú napísanú frázu.',
        'safe_next': 'Ak to chcete naozaj urobiť, použite bezpečnostný tok a postupujte podľa presnej výzvy.',
    },
}
_SLOVAK_OVERVIEW_TITLES = {
    'create_invoice': 'vytvorenie faktúry',
    'show_existing_invoice': 'zobrazenie existujúcej faktúry',
    'edit_existing_invoice': 'úprava existujúcej faktúry',
    'delete_existing_invoice': 'vymazanie existujúcej faktúry',
    'invoice_pdf_generation': 'generovanie PDF faktúry',
    'add_receipt_or_incoming_invoice': 'pridanie bločku alebo prijatej faktúry',
    'show_recent_accounting_documents': 'prehľad nedávnych účtovných dokladov',
    'voice_invoice_intake': 'hlasové zadanie faktúry',
    'send_invoice_email': 'odosielanie faktúr emailom',
    'google_drive_invoice_storage': 'ukladanie faktúr na Google Drive',
    'sms_reminders': 'SMS pripomienky',
    'accounting_export': 'export do účtovníctva',
    'invoice_pdf_custom_template': 'vlastná PDF šablóna faktúry',
    'delete_user_database': 'vymazanie používateľskej databázy',
}

_HELP_CUES = {
    'ako',
    'co',
    'cim',
    'preco',
    'vie',
    'vies',
    'viete',
    'mozes',
    'mozete',
    'da',
    'dokazes',
    'podporujes',
    'podporujete',
    'funguje',
    'can',
    'could',
    'how',
    'what',
    'why',
    'support',
    'supports',
}
_OVERVIEW_PHRASES = (
    'co vies',
    'co dokazes',
    's cim mi vies pomoct',
    's cim viete pomoct',
    'ake funkcie',
    'what can you do',
    'what do you support',
)
_DIRECT_ACTION_GUARD_WORDS = {
    'vytvor',
    'sprav',
    'urob',
    'zrob',
    'pridaj',
    'dodaj',
    'nahraj',
    'posli',
    'vymaz',
    'zmaz',
    'uprav',
    'zobraz',
    'ukaz',
}


def build_product_truth_guidance(
    *,
    user_input_text: str | None,
    resolved_top_level_intent: str | None = None,
    account_context: Mapping[str, Any] | None = None,
) -> str | None:
    """Return Level 2 Product Truth guidance for a conservative InfoHelp topic."""
    capability_id = classify_info_help_capability(
        user_input_text=user_input_text,
        resolved_top_level_intent=resolved_top_level_intent,
    )
    if capability_id is None:
        return None
    if capability_id == 'overview':
        return _build_capability_overview()
    payload = get_safe_answer_payload(capability_id, account_context=account_context)
    return _render_product_truth_payload(payload)


def classify_info_help_capability(
    *,
    user_input_text: str | None,
    resolved_top_level_intent: str | None = None,
) -> str | None:
    """Map only whitelisted informational topics to Product Truth capability ids."""
    normalized = _normalize_text(user_input_text or '')
    if not normalized:
        return None
    tokens = set(normalized.split())
    is_help_like = _is_help_like(normalized, tokens)

    if resolved_top_level_intent in _RESERVED_INTENT_CAPABILITIES:
        return _RESERVED_INTENT_CAPABILITIES[resolved_top_level_intent]

    if any(phrase in normalized for phrase in _OVERVIEW_PHRASES):
        return 'overview'

    if _mentions_email_invoice(normalized, tokens):
        return 'send_invoice_email'
    if _mentions_google_drive(normalized, tokens):
        return 'google_drive_invoice_storage'
    if 'sms' in tokens or 'esemes' in tokens or 'esemesky' in tokens:
        return 'sms_reminders'
    if _mentions_accounting_export(normalized, tokens):
        return 'accounting_export'
    if _mentions_custom_pdf_template(normalized, tokens):
        return 'invoice_pdf_custom_template'
    if _mentions_customization_request(normalized, tokens):
        return 'customization_requests'
    if _mentions_code_agent_handoff(normalized, tokens):
        return 'code_agent_handoff'
    if _mentions_voice_limit(normalized, tokens):
        return 'voice_invoice_intake'
    if _mentions_delete_database_safety(normalized, tokens):
        return 'delete_user_database'
    if _mentions_receipt_how_to(normalized, tokens):
        return 'add_receipt_or_incoming_invoice'
    if _mentions_invoice_how_to(normalized, tokens):
        return 'create_invoice'

    if resolved_top_level_intent in {'unknown', None} and is_help_like and _mentions_info_help(normalized, tokens):
        return 'overview'

    return None


def _render_product_truth_payload(payload: Mapping[str, Any]) -> str:
    capability_id = str(payload.get('capability_id') or '')
    slovak_copy = _SLOVAK_CAPABILITY_COPY.get(capability_id, {})
    title = str(slovak_copy.get('title') or 'Táto schopnosť')
    product_status = str(payload.get('product_status') or 'unknown')
    account_status = str(payload.get('account_status') or 'unknown')
    summary = str(slovak_copy.get('summary') or '').strip()
    limitation = str(slovak_copy.get('limitation') or '').strip()
    safe_next = str(slovak_copy.get('safe_next') or '').strip()

    lines = [
        f'{title}: {_STATUS_LABELS.get(product_status, product_status)}.',
    ]
    if account_status != 'ready':
        lines.append(f'Stav účtu: {_ACCOUNT_STATUS_LABELS.get(account_status, account_status)}.')
    if summary:
        lines.append(summary)
    if limitation:
        lines.append('Obmedzenie: ' + limitation)
    if payload.get('requires_external_credentials'):
        lines.append('Vyžadovalo by to externé prístupy alebo samostatnú integráciu; v aktuálnej verzii to nie je nastavené.')
    if payload.get('dangerous'):
        lines.append('Je to citlivá alebo deštruktívna oblasť, preto musí zostať za deterministickou bezpečnostnou bránou.')
    missing_setup_keys = [str(item) for item in payload.get('missing_setup_keys') or ()]
    if missing_setup_keys:
        lines.append('Chýba nastavenie: ' + ', '.join(missing_setup_keys) + '.')
    if safe_next:
        lines.append('Bezpečný ďalší krok: ' + safe_next)
    if payload.get('customization_allowed'):
        lines.append('Môžem to pomenovať ako budúcu úpravu, ale v tomto chate teraz nevytvorím uloženú požiadavku.')

    return '\n\n'.join(lines)


def _build_capability_overview() -> str:
    capabilities = {capability.capability_id: capability for capability in list_capabilities()}
    lines = ['Overený prehľad podľa Product Truth:']
    for capability_id in _PRODUCT_TRUTH_OVERVIEW_IDS:
        capability = capabilities.get(capability_id)
        if capability is None:
            continue
        status = _STATUS_LABELS.get(capability.status.value, capability.status.value)
        title = _SLOVAK_OVERVIEW_TITLES.get(capability.capability_id, capability.capability_id)
        lines.append(f'- {title}: {status}')
    lines.append('Ak sa pýtate na konkrétnu funkciu, napíšte ju priamo a odpoviem podľa Product Truth.')
    return '\n'.join(lines)


def _normalize_text(text: str) -> str:
    stripped = text.strip().lower()
    without_diacritics = ''.join(
        char for char in unicodedata.normalize('NFKD', stripped) if not unicodedata.combining(char)
    )
    return re.sub(r'[^a-z0-9а-яіїєґ\s]+', ' ', without_diacritics).strip()


def _is_help_like(normalized: str, tokens: set[str]) -> bool:
    return '?' in normalized or bool(tokens.intersection(_HELP_CUES)) or any(
        phrase in normalized for phrase in _OVERVIEW_PHRASES
    )


def _mentions_email_invoice(normalized: str, tokens: set[str]) -> bool:
    return (
        (tokens.intersection({'email', 'mail', 'gmail'}) or any(token.startswith('email') for token in tokens))
        and tokens.intersection({'fakturu', 'faktura', 'invoice', 'odoslat', 'poslat', 'posli', 'send'})
    )


def _mentions_google_drive(normalized: str, tokens: set[str]) -> bool:
    return (
        ('google' in tokens and ('drive' in tokens or 'disk' in tokens))
        or 'googledrive' in normalized
        or 'google disk' in normalized
    )


def _mentions_accounting_export(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'export', 'exportovat', 'exportujete'})) and bool(
        tokens.intersection(
            {
                'uctovnictva',
                'uctovnictvo',
                'uctovny',
                'uctovneho',
                'podklady',
                'accounting',
                'pohoda',
                'omega',
            }
        )
    )


def _mentions_custom_pdf_template(normalized: str, tokens: set[str]) -> bool:
    return (
        'pdf' in tokens
        and bool(tokens.intersection({'sablona', 'sablonu', 'template', 'vzor'}))
        and bool(
            tokens.intersection(
                {'stara', 'vlastna', 'vlastnu', 'custom', 'moja', 'moju', 'old', 'upravit', 'zmenit'}
            )
        )
    )


def _mentions_customization_request(normalized: str, tokens: set[str]) -> bool:
    return bool(
        tokens.intersection({'upravu', 'customizaciu', 'customization', 'poziadavku', 'poziadavka', 'vlastnu'})
    ) and bool(
        tokens.intersection({'funkciu', 'feature', 'zmenu', 'request'})
    )


def _mentions_code_agent_handoff(normalized: str, tokens: set[str]) -> bool:
    mentions_code_agent = 'code' in tokens and any(token == 'agent' or token.startswith('agent') for token in tokens)
    return (
        mentions_code_agent
        or ('kod' in tokens and 'agent' in tokens)
        or bool(tokens.intersection({'nasadit', 'deploy', 'merge'}))
    )


def _mentions_voice_limit(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'hlasom', 'voice', 'audio', 'nahovorim', 'diktovat'})) and bool(
        tokens.intersection({'fakturu', 'faktura', 'invoice', 'iban', 'email', 'cislo', 'suma', 'presne'})
    )


def _mentions_delete_database_safety(normalized: str, tokens: set[str]) -> bool:
    if not tokens.intersection({'databazu', 'database', 'udaje', 'ucet'}):
        return False
    if not tokens.intersection({'vymaz', 'vymazat', 'vymazem', 'zmaz', 'zmazat', 'zmazem', 'delete', 'odstranit', 'zrusit'}):
        return False
    return bool(tokens.intersection(_HELP_CUES)) or normalized.startswith('ako ')


def _mentions_receipt_how_to(normalized: str, tokens: set[str]) -> bool:
    if not bool(tokens.intersection({'blocek', 'blocky', 'doklad', 'receipt', 'prijatu'})):
        return False
    return bool(tokens.intersection({'ako', 'how', 'pridam', 'nahrat', 'nahram', 'upload'}))


def _mentions_invoice_how_to(normalized: str, tokens: set[str]) -> bool:
    if not tokens.intersection({'fakturu', 'faktura', 'invoice'}):
        return False
    if bool(tokens.intersection(_DIRECT_ACTION_GUARD_WORDS)):
        return False
    return bool(tokens.intersection({'ako', 'how'})) or 'ako vytvorim' in normalized or 'how do i create' in normalized


def _mentions_info_help(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'pomoc', 'help', 'funkcie', 'capabilities'})) or any(
        phrase in normalized for phrase in _OVERVIEW_PHRASES
    )


def build_top_level_unknown_guidance(*, user_input_text: str | None = None) -> str:
    """Build deterministic Phase 1 guidance for idle top-level unknown input."""
    return (
        'Nerozumiem, čo chcete spraviť.\n\n'
        'Môžem vám pomôcť napríklad s týmito vecami:\n'
        '- vytvoriť faktúru,\n'
        '- zobraziť alebo upraviť existujúcu faktúru,\n'
        '- pridať kontakt,\n'
        '- upraviť môj profil,\n'
        '- pridať službu používanú vo faktúrach,\n'
        '- pridať bloček alebo prijatú faktúru.\n\n'
        'Skúste napísať konkrétne, čo chcete urobiť, napríklad „vytvor faktúru“, '
        '„pridaj kontakt“ alebo „pridaj bloček“.'
    )
