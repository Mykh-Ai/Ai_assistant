from __future__ import annotations

from dataclasses import dataclass
import json
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

TRIAGE_KNOWN_PRODUCT_CAPABILITY = 'known_product_capability'
TRIAGE_NEW_BUSINESS_FEATURE_REQUEST = 'new_business_feature_request'
TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE = 'customization_request_candidate'
TRIAGE_ADMIN_REVIEW_CANDIDATE = 'admin_review_candidate'
TRIAGE_OUT_OF_DOMAIN = 'out_of_domain'
TRIAGE_SPAM_OR_ABUSE = 'spam_or_abuse'
TRIAGE_SMALLTALK = 'smalltalk'
TRIAGE_UNCLEAR_NEEDS_CLARIFICATION = 'unclear_needs_clarification'
TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE = 'possible_product_truth_candidate'
TRIAGE_UNKNOWN = 'unknown'

ALLOWED_INFO_HELP_TRIAGE_CLASSES = (
    TRIAGE_KNOWN_PRODUCT_CAPABILITY,
    TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
    TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE,
    TRIAGE_ADMIN_REVIEW_CANDIDATE,
    TRIAGE_OUT_OF_DOMAIN,
    TRIAGE_SPAM_OR_ABUSE,
    TRIAGE_SMALLTALK,
    TRIAGE_UNCLEAR_NEEDS_CLARIFICATION,
    TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE,
    TRIAGE_UNKNOWN,
)

ALLOWED_INFO_HELP_TOPIC_IDS = (
    'product_capability',
    'new_business_feature',
    'customization_request',
    'admin_review',
    'out_of_domain',
    'spam_or_abuse',
    'smalltalk',
    'clarification',
    'possible_product_truth_candidate',
    TRIAGE_UNKNOWN,
)

_TRIAGE_TOPIC_BY_CLASS = {
    TRIAGE_KNOWN_PRODUCT_CAPABILITY: 'product_capability',
    TRIAGE_NEW_BUSINESS_FEATURE_REQUEST: 'new_business_feature',
    TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE: 'customization_request',
    TRIAGE_ADMIN_REVIEW_CANDIDATE: 'admin_review',
    TRIAGE_OUT_OF_DOMAIN: 'out_of_domain',
    TRIAGE_SPAM_OR_ABUSE: 'spam_or_abuse',
    TRIAGE_SMALLTALK: 'smalltalk',
    TRIAGE_UNCLEAR_NEEDS_CLARIFICATION: 'clarification',
    TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE: 'possible_product_truth_candidate',
    TRIAGE_UNKNOWN: TRIAGE_UNKNOWN,
}


@dataclass(frozen=True)
class InfoHelpTriageResult:
    capability_id: str = 'unknown'
    topic_id: str = 'unknown'
    triage_class: str = TRIAGE_UNKNOWN
    confidence: float = 0.0
    needs_clarification: bool = False


def parse_info_help_triage_model_output(
    raw_model_output: str,
    *,
    allowed_capability_ids: tuple[str, ...] | list[str] | None = None,
    allowed_topic_ids: tuple[str, ...] | list[str] | None = None,
) -> InfoHelpTriageResult:
    """Validate bounded model classification output without accepting answer text."""
    allowed_capabilities = set(allowed_capability_ids or _known_capability_ids())
    allowed_topics = set(allowed_topic_ids or ALLOWED_INFO_HELP_TOPIC_IDS)
    try:
        parsed = json.loads(raw_model_output or '{}')
    except (TypeError, json.JSONDecodeError):
        return InfoHelpTriageResult()
    if not isinstance(parsed, dict):
        return InfoHelpTriageResult()

    capability_id = str(parsed.get('capability_id') or 'unknown').strip()
    if capability_id not in allowed_capabilities:
        capability_id = 'unknown'

    triage_class = str(parsed.get('triage_class') or TRIAGE_UNKNOWN).strip()
    if triage_class not in ALLOWED_INFO_HELP_TRIAGE_CLASSES:
        triage_class = TRIAGE_UNKNOWN
    if triage_class == TRIAGE_KNOWN_PRODUCT_CAPABILITY and capability_id == 'unknown':
        triage_class = TRIAGE_UNKNOWN
    if capability_id != 'unknown':
        triage_class = TRIAGE_KNOWN_PRODUCT_CAPABILITY

    topic_id = str(parsed.get('topic_id') or _TRIAGE_TOPIC_BY_CLASS.get(triage_class, TRIAGE_UNKNOWN)).strip()
    if topic_id not in allowed_topics:
        topic_id = _TRIAGE_TOPIC_BY_CLASS.get(triage_class, TRIAGE_UNKNOWN)
    if topic_id not in allowed_topics:
        topic_id = TRIAGE_UNKNOWN

    confidence = _bounded_confidence(parsed.get('confidence'))
    needs_clarification = bool(parsed.get('needs_clarification')) or triage_class == TRIAGE_UNCLEAR_NEEDS_CLARIFICATION
    return InfoHelpTriageResult(
        capability_id=capability_id,
        topic_id=topic_id,
        triage_class=triage_class,
        confidence=confidence,
        needs_clarification=needs_clarification,
    )


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


def classify_info_help_triage(*, user_input_text: str | None) -> InfoHelpTriageResult:
    """Classify unresolved InfoHelp input into Python-owned safe triage classes."""
    capability_id = classify_info_help_capability(user_input_text=user_input_text)
    if capability_id is not None and capability_id != 'overview':
        return InfoHelpTriageResult(
            capability_id=capability_id,
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.9,
        )
    if capability_id == 'overview':
        return InfoHelpTriageResult(
            capability_id='unknown',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.9,
        )

    raw_text = user_input_text or ''
    normalized = _normalize_text(raw_text)
    if not normalized:
        if raw_text.strip():
            return _triage_result(TRIAGE_SPAM_OR_ABUSE, confidence=0.75)
        return InfoHelpTriageResult(needs_clarification=True)
    tokens = set(normalized.split())

    if _is_noise_or_abuse(normalized, tokens):
        return _triage_result(TRIAGE_SPAM_OR_ABUSE, confidence=0.75)
    if _is_smalltalk(normalized, tokens):
        return _triage_result(TRIAGE_SMALLTALK, confidence=0.85)
    if _is_unclear_request(normalized, tokens):
        return _triage_result(TRIAGE_UNCLEAR_NEEDS_CLARIFICATION, confidence=0.85, needs_clarification=True)
    if _is_out_of_domain(normalized, tokens):
        return _triage_result(TRIAGE_OUT_OF_DOMAIN, confidence=0.85)
    if _is_admin_review_request(normalized, tokens):
        return _triage_result(TRIAGE_ADMIN_REVIEW_CANDIDATE, confidence=0.8)
    if _is_new_business_feature_request(normalized, tokens):
        return _triage_result(TRIAGE_NEW_BUSINESS_FEATURE_REQUEST, confidence=0.8)
    if _is_customization_candidate(normalized, tokens):
        return _triage_result(TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE, confidence=0.75)
    if _is_possible_product_truth_candidate(normalized, tokens):
        return _triage_result(TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE, confidence=0.6)
    return InfoHelpTriageResult()


def build_info_help_triage_guidance(
    *,
    user_input_text: str | None,
    account_context: Mapping[str, Any] | None = None,
) -> str | None:
    """Render a safe non-persistent answer for bounded InfoHelp/Triage v1."""
    result = classify_info_help_triage(user_input_text=user_input_text)
    if result.triage_class == TRIAGE_KNOWN_PRODUCT_CAPABILITY:
        if result.capability_id != 'unknown':
            payload = get_safe_answer_payload(result.capability_id, account_context=account_context)
            return _render_product_truth_payload(payload)
        return _build_capability_overview()
    if result.triage_class == TRIAGE_NEW_BUSINESS_FEATURE_REQUEST:
        return (
            'Toto vyzer\u00e1 ako po\u017eiadavka na nov\u00fa biznis funkciu. '
            'V aktu\u00e1lnom runtime ju neviem potvrdi\u0165 ako podporovan\u00fa.\n\n'
            'Ukladanie po\u017eiadaviek zatia\u013e nie je zapnut\u00e9, preto som ni\u010d neulo\u017eil ani neposlal spr\u00e1vcovi.'
        )
    if result.triage_class == TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE:
        return (
            'Toto vyzer\u00e1 ako po\u017eiadavka na \u00fapravu alebo prisp\u00f4sobenie. '
            'V tomto chate zatia\u013e neexistuje potvrden\u00fd tok na ulo\u017eenie takejto po\u017eiadavky.\n\n'
            'Ni\u010d som neulo\u017eil. Ak chcete, pop\u00ed\u0161te presne, ak\u00fd biznis v\u00fdsledok potrebujete.'
        )
    if result.triage_class == TRIAGE_ADMIN_REVIEW_CANDIDATE:
        return (
            'Toto vyzer\u00e1 ako po\u017eiadavka pre spr\u00e1vcu alebo v\u00fdvoj\u00e1ra. '
            'Automatick\u00e9 odoslanie spr\u00e1vcovi zatia\u013e nie je zapnut\u00e9.\n\n'
            'Ni\u010d som neposlal ani neulo\u017eil. Nap\u00ed\u0161te pros\u00edm konkr\u00e9tnu po\u017eiadavku, ktor\u00fa chcete nesk\u00f4r odovzda\u0165.'
        )
    if result.triage_class == TRIAGE_OUT_OF_DOMAIN:
        return (
            'Toto je mimo rozsahu OfficeFlow/FakturaBotu. '
            'Viem pom\u00e1ha\u0165 s fakt\u00farami, kontaktmi, profilom dod\u00e1vate\u013ea, slu\u017ebami a \u00fa\u010dtovn\u00fdmi dokladmi.'
        )
    if result.triage_class == TRIAGE_SPAM_OR_ABUSE:
        return 'Tomuto vstupu nerozumiem. Sk\u00faste nap\u00edsa\u0165 konkr\u00e9tnu biznis \u00falohu alebo ot\u00e1zku k FakturaBotu.'
    if result.triage_class == TRIAGE_SMALLTALK:
        return (
            'Som pripraven\u00fd pom\u00f4c\u0165 s biznis \u00falohami vo FakturaBote. '
            'M\u00f4\u017eete sa op\u00fdta\u0165 na fakt\u00fary, kontakty, slu\u017eby, PDF alebo \u00fa\u010dtovn\u00e9 doklady.'
        )
    if result.triage_class == TRIAGE_UNCLEAR_NEEDS_CLARIFICATION:
        return 'Nie je jasn\u00e9, ak\u00fa biznis \u00falohu mysl\u00edte. Nap\u00ed\u0161te pros\u00edm konkr\u00e9tne, \u010do m\u00e1m spravi\u0165.'
    if result.triage_class == TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE:
        return (
            'Toto m\u00f4\u017ee by\u0165 ot\u00e1zka na schopnos\u0165 produktu, ale neviem ju bezpe\u010dne priradi\u0165 ku konkr\u00e9tnej Product Truth polo\u017eke.\n\n'
            'Spresnite pros\u00edm, \u010di sa p\u00fdtate na fakt\u00fary, PDF, kontakty, slu\u017eby, \u00fa\u010dtovn\u00e9 doklady alebo nastavenie \u00fa\u010dtu.'
        )
    return None


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


def _known_capability_ids() -> tuple[str, ...]:
    return tuple(capability.capability_id for capability in list_capabilities())


def _bounded_confidence(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed < 0:
        return 0.0
    if parsed > 1:
        return 1.0
    return parsed


def _triage_result(
    triage_class: str,
    *,
    confidence: float,
    needs_clarification: bool = False,
) -> InfoHelpTriageResult:
    return InfoHelpTriageResult(
        topic_id=_TRIAGE_TOPIC_BY_CLASS.get(triage_class, TRIAGE_UNKNOWN),
        triage_class=triage_class,
        confidence=confidence,
        needs_clarification=needs_clarification,
    )


def _is_noise_or_abuse(normalized: str, tokens: set[str]) -> bool:
    if not tokens:
        return True
    if len(normalized) <= 2:
        return True
    alpha_count = sum(1 for char in normalized if char.isalpha())
    if alpha_count == 0:
        return True
    return normalized in {'asdf', 'qwerty', 'bla bla bla'}


def _is_smalltalk(normalized: str, tokens: set[str]) -> bool:
    return (
        normalized in {'ako sa mas', 'ako sa mate', 'how are you', 'jak sa mas'}
        or ('ako' in tokens and 'mas' in tokens and len(tokens) <= 4)
        or ('справи' in tokens and len(tokens) <= 4)
        or ('дела' in tokens and len(tokens) <= 4)
    )


def _is_unclear_request(normalized: str, tokens: set[str]) -> bool:
    return normalized in {
        'urob mi to',
        'sprav mi to',
        'zrob mi to',
        'urob to',
        'sprav to',
        'do it',
        'зроби це',
        'сделай это',
    } or (tokens.intersection({'urob', 'sprav', 'zrob', 'сделай', 'зроби'}) and tokens <= {
        'urob',
        'sprav',
        'zrob',
        'mi',
        'to',
        'сделай',
        'зроби',
        'це',
        'это',
    })


def _is_out_of_domain(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'pocasie', 'weather', 'forecast', 'погода', 'погоду'}))


def _is_admin_review_request(normalized: str, tokens: set[str]) -> bool:
    mentions_admin = bool(tokens.intersection({'adminovi', 'admin', 'spravcovi', 'spravca', 'админу', 'адміну'}))
    return mentions_admin and bool(
        tokens.intersection({'povedz', 'posli', 'odosli', 'napis', 'potrebujem', 'скажи', 'передай'})
    )


def _is_new_business_feature_request(normalized: str, tokens: set[str]) -> bool:
    mentions_revenue_overview = bool(tokens.intersection({'trzieb', 'trzby', 'revenue', 'vynosov', 'выручки', 'виручки'})) and bool(
        tokens.intersection({'prehlad', 'report', 'vykaz', 'overview', 'отчет', 'звіт'})
    )
    mentions_month = bool(tokens.intersection({'mesiac', 'mesacny', 'monthly', 'месяц', 'місяць'}))
    return mentions_revenue_overview or (
        mentions_month
        and bool(tokens.intersection({'prehlad', 'report', 'vykaz', 'overview', 'отчет', 'звіт'}))
        and not tokens.intersection({'fakturu', 'faktura', 'invoice'})
    )


def _is_customization_candidate(normalized: str, tokens: set[str]) -> bool:
    if bool(tokens.intersection({'automaticke', 'automaticky', 'automatic', 'автоматичні', 'автоматические'})) and bool(
        tokens.intersection({'pripomienky', 'reminders', 'напоминания', 'нагадування'})
    ):
        return True
    return bool(tokens.intersection({'potrebujem', 'chcem', 'хочу', 'потрібно'})) and bool(
        tokens.intersection({'upravu', 'prisposobit', 'custom', 'vlastne', 'vlastnu', 'zmenu'})
    )


def _is_possible_product_truth_candidate(normalized: str, tokens: set[str]) -> bool:
    if not _is_help_like(normalized, tokens):
        return False
    return bool(
        tokens.intersection(
            {
                'faktura',
                'fakturu',
                'faktury',
                'invoice',
                'pdf',
                'kontakt',
                'doklad',
                'blocky',
                'uctovnictvo',
                'uctovne',
                'sluzby',
                'profil',
            }
        )
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
