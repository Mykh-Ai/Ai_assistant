from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from typing import Mapping

from bot.services.info_help_action_registry import get_info_help_action
from bot.services.product_truth import list_capabilities


INFO_HELP_INTENT_BUSINESS_ACTION = 'business_action_request'
INFO_HELP_INTENT_CAPABILITY_QUESTION = 'capability_question'
INFO_HELP_INTENT_COMMAND_TYPO = 'probable_command_typo'
INFO_HELP_INTENT_INCOMPLETE = 'incomplete_intent'
INFO_HELP_INTENT_CONVERSATIONAL = 'conversational_followup'
INFO_HELP_INTENT_ACTIVE_FLOW = 'active_flow_question'
INFO_HELP_INTENT_ACTIVE_EXPECTED = 'active_expected_input_question'
INFO_HELP_INTENT_NEW_FEATURE = 'new_business_feature_request'
INFO_HELP_INTENT_SMALLTALK = 'smalltalk'
INFO_HELP_INTENT_OUT_OF_DOMAIN = 'out_of_domain'
INFO_HELP_INTENT_GENUINELY_UNCLEAR = 'genuinely_unclear'

INFO_HELP_SPEECH_EXECUTE = 'execute_request'
INFO_HELP_SPEECH_CAPABILITY_QUESTION = 'capability_question'
INFO_HELP_SPEECH_CORRECTION = 'correction'
INFO_HELP_SPEECH_CLARIFICATION = 'clarification_answer'
INFO_HELP_SPEECH_INFORMATIONAL = 'informational_question'
INFO_HELP_SPEECH_UNKNOWN = 'unknown'

_INTENT_KINDS = {
    INFO_HELP_INTENT_BUSINESS_ACTION, INFO_HELP_INTENT_CAPABILITY_QUESTION,
    INFO_HELP_INTENT_COMMAND_TYPO, INFO_HELP_INTENT_INCOMPLETE,
    INFO_HELP_INTENT_CONVERSATIONAL, INFO_HELP_INTENT_ACTIVE_FLOW,
    INFO_HELP_INTENT_ACTIVE_EXPECTED, INFO_HELP_INTENT_NEW_FEATURE,
    INFO_HELP_INTENT_SMALLTALK, INFO_HELP_INTENT_OUT_OF_DOMAIN,
    INFO_HELP_INTENT_GENUINELY_UNCLEAR,
}
_SPEECH_ACTS = {
    INFO_HELP_SPEECH_EXECUTE, INFO_HELP_SPEECH_CAPABILITY_QUESTION,
    INFO_HELP_SPEECH_CORRECTION, INFO_HELP_SPEECH_CLARIFICATION,
    INFO_HELP_SPEECH_INFORMATIONAL, INFO_HELP_SPEECH_UNKNOWN,
}
_DOMAINS = {
    'invoices', 'accounting_documents', 'contacts', 'supplier_profile',
    'service_aliases', 'work_time', 'access_control', 'workspace_setup',
    'customization', 'product', 'unknown',
}
_OBJECTS = {
    'invoice', 'receipt', 'incoming_invoice', 'accounting_document', 'contact',
    'supplier_profile', 'service_alias', 'work_time_entry', 'work_time_report',
    'user_data', 'workspace', 'product_capability', 'unknown',
}
_OPERATIONS = {
    'create', 'show', 'show_recent', 'edit', 'delete', 'mark_paid', 'analyze',
    'generate', 'switch', 'explain', 'unknown',
}
KNOWN_INFO_HELP_COMMANDS = (
    '/start', '/menu', '/cancel', '/invoice', '/contact', '/contact_add',
    '/add_kontakt', '/moj_profil', '/upravit_profil', '/blocky', '/blocek',
    '/sluzbu', '/service', '/alias', '/profily', '/dochadzka', '/issue',
)

INFO_HELP_INTENT_KINDS = tuple(sorted(_INTENT_KINDS))
INFO_HELP_SPEECH_ACTS = tuple(sorted(_SPEECH_ACTS))
INFO_HELP_DOMAINS = tuple(sorted(_DOMAINS))
INFO_HELP_OBJECTS = tuple(sorted(_OBJECTS))
INFO_HELP_OPERATIONS = tuple(sorted(_OPERATIONS))
INFO_HELP_MISSING_SLOTS = ('attachment', 'invoice_reference', 'object_kind', 'operation_id')


@dataclass(frozen=True)
class InfoHelpAssistantResult:
    intent_kind: str = INFO_HELP_INTENT_GENUINELY_UNCLEAR
    speech_act: str = INFO_HELP_SPEECH_UNKNOWN
    domain_id: str = 'unknown'
    object_kind: str = 'unknown'
    operation_id: str = 'unknown'
    target_reference: str | None = None
    proposed_action_id: str | None = None
    proposed_capability_id: str | None = None
    probable_command_target: str | None = None
    intent_complete: bool = False
    missing_slots: tuple[str, ...] = ()
    is_correction: bool = False
    negated_objects: tuple[str, ...] = ()
    negated_operations: tuple[str, ...] = ()
    corrected_from_object: str | None = None
    corrected_to_object: str | None = None
    refers_to_active_flow: bool = False
    refers_to_explicit_reply: bool = False
    confidence: float = 0.0
    acknowledgement_sk: str = ''
    clarification_question_sk: str = ''


def parse_info_help_assistant_model_output(raw_model_output: str) -> InfoHelpAssistantResult:
    try:
        parsed = json.loads(raw_model_output or '{}')
    except (TypeError, json.JSONDecodeError):
        return InfoHelpAssistantResult()
    if not isinstance(parsed, dict):
        return InfoHelpAssistantResult()

    intent_kind = str(parsed.get('intent_kind') or '')
    speech_act = str(parsed.get('speech_act') or '')
    domain_id = str(parsed.get('domain_id') or 'unknown')
    object_kind = str(parsed.get('object_kind') or 'unknown')
    operation_id = str(parsed.get('operation_id') or 'unknown')
    if not (
        intent_kind in _INTENT_KINDS
        and speech_act in _SPEECH_ACTS
        and domain_id in _DOMAINS
        and object_kind in _OBJECTS
        and operation_id in _OPERATIONS
    ):
        return InfoHelpAssistantResult(
            acknowledgement_sk=_bounded_text(parsed.get('acknowledgement_sk'), max_length=240)
        )

    action_id = _optional_text(parsed.get('proposed_action_id'), max_length=80)
    if action_id and get_info_help_action(action_id) is None:
        return InfoHelpAssistantResult()
    known_capabilities = {item.capability_id for item in list_capabilities()}
    capability_id = _optional_text(parsed.get('proposed_capability_id'), max_length=100)
    if capability_id and capability_id not in known_capabilities:
        return InfoHelpAssistantResult()
    command = _optional_text(parsed.get('probable_command_target'), max_length=80)
    if command and command not in KNOWN_INFO_HELP_COMMANDS:
        return InfoHelpAssistantResult()
    raw_confidence = parsed.get('confidence')
    confidence = float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 0.0
    if not 0 <= confidence <= 1:
        confidence = 0.0
    acknowledgement = _bounded_text(parsed.get('acknowledgement_sk'), max_length=240)
    if _claims_side_effect(acknowledgement):
        acknowledgement = ''

    return InfoHelpAssistantResult(
        intent_kind=intent_kind,
        speech_act=speech_act,
        domain_id=domain_id,
        object_kind=object_kind,
        operation_id=operation_id,
        target_reference=_optional_text(parsed.get('target_reference'), max_length=120),
        proposed_action_id=action_id,
        proposed_capability_id=capability_id,
        probable_command_target=command,
        intent_complete=bool(parsed.get('intent_complete')),
        missing_slots=_enum_list(parsed.get('missing_slots'), {'invoice_reference', 'operation_id', 'object_kind', 'attachment'}),
        is_correction=bool(parsed.get('is_correction')),
        negated_objects=_enum_list(parsed.get('negated_objects'), _OBJECTS - {'unknown'}),
        negated_operations=_enum_list(parsed.get('negated_operations'), _OPERATIONS - {'unknown'}),
        corrected_from_object=_optional_choice(parsed.get('corrected_from_object'), _OBJECTS - {'unknown'}),
        corrected_to_object=_optional_choice(parsed.get('corrected_to_object'), _OBJECTS - {'unknown'}),
        refers_to_active_flow=bool(parsed.get('refers_to_active_flow')),
        refers_to_explicit_reply=bool(parsed.get('refers_to_explicit_reply')),
        confidence=confidence,
        acknowledgement_sk=acknowledgement,
        clarification_question_sk=_bounded_text(parsed.get('clarification_question_sk'), max_length=240),
    )


def build_info_help_product_truth_view() -> list[dict[str, object]]:
    return [
        {
            'capability_id': item.capability_id,
            'title': item.title,
            'domain': item.domain,
            'product_status': item.status.value,
            'account_status': 'unknown',
            'summary': item.summary_for_user,
            'current_limitations': list(item.current_limitations[:4]),
            'canonical_actions': list(item.canonical_actions),
            'commands': list(item.commands),
            'runtime_owner': bool(item.runtime_owner),
            'safe_next_steps': list(item.safe_next_steps[:3]),
            'customization_allowed': item.customization_allowed,
            'dangerous': item.dangerous,
            'requires_setup': item.requires_setup,
            'requires_admin': item.requires_admin,
            'requires_external_credentials': item.requires_external_credentials,
            'supported_channels': list(item.supported_channels),
            'unsupported_channels': list(item.unsupported_channels),
        }
        for item in list_capabilities()
    ]


def should_run_contextual_info_help(
    *,
    primary_action: str,
    input_text: str,
    input_channel: str = 'text',
    primary_diagnostics: Mapping[str, object] | None = None,
) -> bool:
    if primary_action == 'unknown' or input_channel == 'command' or input_text.lstrip().startswith('/'):
        return True
    semantic = get_info_help_action(primary_action)
    if semantic and semantic.mutation_class in {'mutating', 'destructive'}:
        return True
    normalized = _normalize(input_text)
    wrapped = f' {normalized} '
    if any(token in wrapped for token in (' nie ', ' not ', ' ne ', ' а не ', ' але не ', ' but not ', ' namiesto ', ' замість ')):
        return True
    if input_text.strip().endswith('?') or normalized.startswith(
        ('can ', 'could ', 'do you ', 'vies ', 'viete ', 'mozem ', 'ci mozem ', 'чи можу ', 'можно ли ')
    ):
        return True
    if (
        semantic
        and 'invoice_reference' in semantic.required_slots
        and re.search(r'\d', input_text) is None
    ):
        return True
    slots = (primary_diagnostics or {}).get('slots')
    return bool(
        semantic
        and semantic.required_slots
        and isinstance(slots, Mapping)
        and any(not slots.get(slot) for slot in semantic.required_slots)
    )


def _enum_list(value: object, allowed: set[str]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict.fromkeys(str(item) for item in value[:8] if str(item) in allowed))


def _optional_choice(value: object, allowed: set[str]) -> str | None:
    text = str(value or '')
    return text if text in allowed else None


def _optional_text(value: object, *, max_length: int) -> str | None:
    text = _bounded_text(value, max_length=max_length)
    return text or None


def _bounded_text(value: object, *, max_length: int) -> str:
    return ' '.join(str(value or '').split())[:max_length]


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value.strip().casefold())
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_diacritics).strip()


def _claims_side_effect(value: str) -> bool:
    normalized = _normalize(value)
    return any(
        phrase in normalized
        for phrase in ('som vymazal', 'som odstranil', 'som ulozil', 'som vytvoril', 'bola vymazana', 'bolo ulozene')
    )
