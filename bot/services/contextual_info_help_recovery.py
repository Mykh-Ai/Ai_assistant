from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import secrets
from typing import Any, Callable

from openai import AsyncOpenAI

from bot.services.product_truth import get_capability


GENUINELY_UNCLEAR_MESSAGE = (
    'Tejto správe som nerozumel.\n'
    'Skúste prosím stručne napísať, čo chcete urobiť.'
)
ALLOWED_RECOVERY_OUTCOMES = (
    'resolved_action', 'clarify_candidates', 'describe_active_flow',
    'describe_expected_input', 'unsupported_capability',
    'new_business_feature_request', 'genuinely_unclear',
)
ALLOWED_RECOVERY_FAILURE_CAUSES = (
    'probable_input_error', 'probable_stt_distortion', 'missing_operation',
    'missing_object', 'contextual_continuation', 'active_flow_question',
    'active_flow_mismatch', 'unsupported_capability',
    'ambiguous_between_actions', 'primary_resolver_miss', 'insufficient_signal',
)
_ALLOWED_OPERATIONS = {
    'create', 'show', 'edit', 'delete', 'send', 'mark_paid', 'analyze',
    'configure', 'switch', 'track', 'report', 'unknown',
}
_ACTION_METADATA: dict[str, dict[str, str | bool]] = {
    'start': {'label_sk': 'Zobraziť stav a začiatok', 'domain': 'general', 'operation': 'show', 'mutation': False, 'capability_id': 'info_help'},
    'switch_business_profile': {'label_sk': 'Prepnúť firemný profil', 'domain': 'supplier', 'operation': 'switch', 'mutation': True, 'capability_id': 'business_profiles'},
    'create_invoice': {'label_sk': 'Vytvoriť faktúru', 'domain': 'invoice', 'operation': 'create', 'mutation': True, 'capability_id': 'create_invoice'},
    'show_existing_invoice': {'label_sk': 'Zobraziť faktúru', 'domain': 'invoice', 'operation': 'show', 'mutation': False, 'capability_id': 'show_existing_invoice'},
    'send_invoice': {'label_sk': 'Odoslať faktúru emailom', 'domain': 'invoice', 'operation': 'send', 'mutation': True, 'capability_id': 'send_invoice_email'},
    'invoice_analytics': {'label_sk': 'Analyzovať faktúry', 'domain': 'invoice', 'operation': 'analyze', 'mutation': False, 'capability_id': 'invoice_analytics'},
    'accounting_document_analytics': {'label_sk': 'Analyzovať účtovné doklady', 'domain': 'accounting_document', 'operation': 'analyze', 'mutation': False, 'capability_id': 'accounting_document_analytics'},
    'show_supplier_profile': {'label_sk': 'Zobraziť profil dodávateľa', 'domain': 'supplier', 'operation': 'show', 'mutation': False, 'capability_id': 'supplier_profile'},
    'edit_supplier': {'label_sk': 'Upraviť profil dodávateľa', 'domain': 'supplier', 'operation': 'edit', 'mutation': True, 'capability_id': 'edit_supplier_profile'},
    'add_contact': {'label_sk': 'Pridať kontakt', 'domain': 'contact', 'operation': 'create', 'mutation': True, 'capability_id': 'contacts'},
    'add_service_alias': {'label_sk': 'Pridať službu', 'domain': 'service', 'operation': 'create', 'mutation': True, 'capability_id': 'service_aliases'},
    'show_recent_accounting_documents': {'label_sk': 'Zobraziť posledné doklady', 'domain': 'accounting_document', 'operation': 'show', 'mutation': False, 'capability_id': 'show_recent_accounting_documents'},
    'add_receipt': {'label_sk': 'Pridať účtovný doklad', 'domain': 'accounting_document', 'operation': 'create', 'mutation': True, 'capability_id': 'add_receipt_or_incoming_invoice'},
    'delete_user_database': {'label_sk': 'Vymazať používateľskú databázu', 'domain': 'account', 'operation': 'delete', 'mutation': True, 'capability_id': 'delete_user_database'},
    'open_work_day': {'label_sk': 'Začať pracovný deň', 'domain': 'work_time', 'operation': 'track', 'mutation': True, 'capability_id': 'work_time_tracking'},
    'close_work_day': {'label_sk': 'Ukončiť pracovný deň', 'domain': 'work_time', 'operation': 'track', 'mutation': True, 'capability_id': 'work_time_tracking'},
    'add_work_time_entry': {'label_sk': 'Pridať časový záznam', 'domain': 'work_time', 'operation': 'create', 'mutation': True, 'capability_id': 'work_time_tracking'},
    'generate_work_time_report': {'label_sk': 'Vytvoriť výkaz dochádzky', 'domain': 'work_time', 'operation': 'report', 'mutation': False, 'capability_id': 'work_time_tracking'},
    'delete_work_time_month': {'label_sk': 'Vymazať mesiac dochádzky', 'domain': 'work_time', 'operation': 'delete', 'mutation': True, 'capability_id': 'work_time_tracking'},
    'update_work_time_lunch_break': {'label_sk': 'Upraviť obednú prestávku', 'domain': 'work_time', 'operation': 'edit', 'mutation': True, 'capability_id': 'work_time_tracking'},
    'edit_existing_invoice': {'label_sk': 'Upraviť existujúcu faktúru', 'domain': 'invoice', 'operation': 'edit', 'mutation': True, 'capability_id': 'edit_existing_invoice'},
    'delete_existing_invoice': {'label_sk': 'Vymazať existujúcu faktúru', 'domain': 'invoice', 'operation': 'delete', 'mutation': True, 'capability_id': 'delete_existing_invoice'},
    'mark_existing_invoice_paid': {'label_sk': 'Označiť faktúru ako uhradenú', 'domain': 'invoice', 'operation': 'mark_paid', 'mutation': True, 'capability_id': 'mark_existing_invoice_paid'},
}


@dataclass(frozen=True)
class ContextualRecoveryResult:
    recovery_outcome: str = 'genuinely_unclear'
    action_id: str | None = None
    candidate_action_ids: tuple[str, ...] = ()
    capability_id: str | None = None
    object_domain: str = 'unknown'
    operation: str = 'unknown'
    refers_to_active_flow: bool = False
    confidence: float = 0.0
    needs_clarification: bool = True
    failure_cause: str = 'insufficient_signal'
    validation_error: str | None = None

    @property
    def outcome(self) -> str:
        return self.recovery_outcome

    @property
    def references_active_state(self) -> bool:
        return self.refers_to_active_flow


@dataclass(frozen=True)
class RecoverySelectionRecord:
    token: str
    user_id: int
    chat_id: int
    workspace_id: str | None
    candidate_action_ids: tuple[str, ...]
    created_at: datetime


_WORKSPACE_NOT_PROVIDED = object()


class ContextualRecoveryStore:
    def __init__(self, *, clock: Callable[[], datetime] | None = None,
                 ttl: timedelta = timedelta(minutes=10)) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._ttl = min(ttl, timedelta(minutes=10))
        self._records: dict[str, RecoverySelectionRecord] = {}
        self._consumed: dict[str, datetime] = {}

    def create(self, *, user_id: int, chat_id: int, workspace_id: str | int | None,
               candidate_action_ids: list[str] | tuple[str, ...]) -> str:
        candidates = tuple(action for action in candidate_action_ids if action in _ACTION_METADATA)[:4]
        if not candidates:
            raise ValueError('recovery_candidates_required')
        self._prune()
        token = secrets.token_urlsafe(9).replace(':', '_')
        self._records[token] = RecoverySelectionRecord(
            token, int(user_id), int(chat_id), _workspace_key(workspace_id),
            candidates, _utc(self._clock())
        )
        return token

    def consume(self, token: str, *, user_id: int, chat_id: int, index: int,
                workspace_id: str | int | None | object = _WORKSPACE_NOT_PROVIDED) -> str | None:
        status, action = self.consume_with_status(
            token, user_id=user_id, chat_id=chat_id, index=index,
            workspace_id=workspace_id,
        )
        return action if status == 'consumed' else None

    def consume_with_status(
        self,
        token: str,
        *,
        user_id: int,
        chat_id: int,
        index: int,
        workspace_id: str | int | None | object = _WORKSPACE_NOT_PROVIDED,
    ) -> tuple[str, str | None]:
        now = _utc(self._clock())
        record = self._records.get(token)
        if record is None:
            self._prune()
            return ('duplicate', None) if token in self._consumed else ('missing', None)
        if now - record.created_at > self._ttl:
            self._records.pop(token, None)
            return 'expired', None
        if record.user_id != int(user_id) or record.chat_id != int(chat_id):
            return 'forbidden', None
        if (workspace_id is not _WORKSPACE_NOT_PROVIDED
                and record.workspace_id != _workspace_key(workspace_id)):
            return 'forbidden', None
        if index < 0 or index >= len(record.candidate_action_ids):
            return 'invalid_index', None
        action = record.candidate_action_ids[index]
        self._records.pop(token, None)
        self._consumed[token] = now
        return 'consumed', action

    def _prune(self) -> None:
        now = _utc(self._clock())
        for token, record in list(self._records.items()):
            if now - record.created_at > self._ttl:
                self._records.pop(token, None)
        for token, consumed_at in list(self._consumed.items()):
            if now - consumed_at > self._ttl:
                self._consumed.pop(token, None)


contextual_recovery_store = ContextualRecoveryStore()


def action_metadata(action_id: str) -> dict[str, str | bool] | None:
    metadata = _ACTION_METADATA.get(action_id)
    return dict(metadata) if metadata else None


def action_label(action_id: str) -> str:
    metadata = _ACTION_METADATA.get(action_id)
    return str(metadata['label_sk']) if metadata else action_id


def default_recovery_action_ids() -> tuple[str, ...]:
    return tuple(_ACTION_METADATA)


def default_recovery_capability_ids() -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item['capability_id']) for item in _ACTION_METADATA.values()))


def build_contextual_recovery_payload(*, user_input: str, input_channel: str,
                                      recent_turns: list[dict[str, object]],
                                      active_state_descriptor: object | None,
                                      action_ids: list[str] | tuple[str, ...],
                                      capability_ids: list[str] | tuple[str, ...]) -> dict[str, Any]:
    actions = []
    for action_id in action_ids:
        metadata = _ACTION_METADATA.get(action_id)
        if metadata is not None:
            actions.append({'action_id': action_id, **metadata})
    capabilities = []
    for capability_id in capability_ids:
        truth_result = get_capability(capability_id)
        capability = truth_result.capability
        capabilities.append({
            'capability_id': capability_id, 'title': capability.title,
            'domain': capability.domain, 'status': truth_result.product_status.value,
            'mutation_class': 'python_owned',
        })
    converter = getattr(active_state_descriptor, 'to_prompt_dict', None)
    descriptor = converter() if callable(converter) else active_state_descriptor
    bounded_turns: list[dict[str, object]] = []
    for raw_turn in recent_turns:
        if not isinstance(raw_turn, dict) or raw_turn.get('role') not in {'user', 'bot'}:
            continue
        turn_text = str(raw_turn.get('text') or '').strip()
        if not turn_text:
            continue
        turn: dict[str, object] = {
            'role': raw_turn['role'],
            'text': turn_text,
            'channel': str(raw_turn.get('channel') or 'text'),
        }
        labels = raw_turn.get('visible_button_labels')
        if isinstance(labels, list):
            turn['visible_button_labels'] = [str(label) for label in labels if str(label).strip()]
        bounded_turns.append(turn)
    normalized_channel = 'voice_stt' if input_channel == 'voice' else input_channel
    return {
        'context_name': 'contextual_info_help_recovery_v1',
        'current_input': str(user_input).strip(),
        'input_channel': normalized_channel if normalized_channel in {'text', 'command', 'voice_stt', 'callback'} else 'text',
        'recent_turns': bounded_turns[-6:],
        'active_state_descriptor': descriptor,
        'canonical_actions': actions,
        'neighboring_action_ids': [item['action_id'] for item in actions],
        'product_truth_capabilities': capabilities,
        'allowed_outcomes': list(ALLOWED_RECOVERY_OUTCOMES),
        'allowed_failure_causes': list(ALLOWED_RECOVERY_FAILURE_CAUSES),
        'allowed_operations': sorted(_ALLOWED_OPERATIONS),
        'expected_output_fields': [
            'recovery_outcome', 'failure_cause', 'action_id', 'candidate_action_ids',
            'capability_id', 'object_domain', 'operation', 'refers_to_active_flow',
            'confidence', 'needs_clarification',
        ],
    }


def parse_contextual_recovery_result(raw: str | dict[str, Any]) -> ContextualRecoveryResult:
    try:
        payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ContextualRecoveryResult(validation_error='invalid_json')
    outcome = payload.get('recovery_outcome')
    if outcome not in ALLOWED_RECOVERY_OUTCOMES:
        return ContextualRecoveryResult(validation_error='invalid_outcome')
    failure_cause = payload.get('failure_cause')
    if failure_cause not in ALLOWED_RECOVERY_FAILURE_CAUSES:
        return ContextualRecoveryResult(validation_error='invalid_failure_cause')
    action_id = payload.get('action_id')
    if not isinstance(action_id, str) or action_id not in _ACTION_METADATA:
        action_id = None
    domain = str(payload.get('object_domain') or 'unknown').strip().casefold()
    if domain not in {str(item['domain']) for item in _ACTION_METADATA.values()}:
        domain = 'unknown'
    operation = str(payload.get('operation') or 'unknown').strip().casefold()
    if operation not in _ALLOWED_OPERATIONS:
        operation = 'unknown'
    candidates: list[str] = []
    raw_candidates = payload.get('candidate_action_ids')
    if isinstance(raw_candidates, list):
        for candidate in raw_candidates:
            metadata = _ACTION_METADATA.get(candidate) if isinstance(candidate, str) else None
            if metadata is None or candidate in candidates:
                continue
            truth = get_capability(str(metadata['capability_id']))
            if truth.product_status.value in {'planned', 'unsupported', 'unknown'}:
                continue

            if domain != 'unknown' and metadata['domain'] != domain:
                continue
            candidates.append(candidate)
            if len(candidates) == 4:
                break
    capability_id = payload.get('capability_id')
    if isinstance(capability_id, str):
        truth_result = get_capability(capability_id)
        capability = truth_result.capability
        if capability.capability_id != capability_id or truth_result.product_status.value == 'unknown':
            capability_id = None
    else:
        capability_id = None
    if outcome == 'resolved_action' and action_id is None:
        return ContextualRecoveryResult(validation_error='unknown_action')
    if outcome == 'clarify_candidates' and not candidates:
        return ContextualRecoveryResult(validation_error='no_valid_candidates')
    if outcome == 'unsupported_capability' and capability_id is None:
        return ContextualRecoveryResult(validation_error='unknown_capability')
    try:
        confidence = min(1.0, max(0.0, float(payload.get('confidence', 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return ContextualRecoveryResult(
        recovery_outcome=outcome, action_id=action_id, candidate_action_ids=tuple(candidates),
        capability_id=capability_id, object_domain=domain, operation=operation,
        refers_to_active_flow=payload.get('refers_to_active_flow') is True,
        confidence=confidence, needs_clarification=payload.get('needs_clarification') is not False,
        failure_cause=failure_cause,
    )


async def resolve_contextual_recovery(*, user_input: str, input_channel: str,
                                      recent_turns: list[dict[str, object]],
                                      active_state_descriptor: object | None,
                                      action_ids: list[str] | tuple[str, ...],
                                      capability_ids: list[str] | tuple[str, ...],
                                      api_key: str | None, model: str,
                                      timeout_seconds: float = 8.0) -> ContextualRecoveryResult:
    if not user_input.strip() or not api_key or not api_key.startswith('sk-'):
        return ContextualRecoveryResult(validation_error='model_unavailable')
    payload = build_contextual_recovery_payload(
        user_input=user_input, input_channel=input_channel, recent_turns=recent_turns,
        active_state_descriptor=active_state_descriptor, action_ids=action_ids,
        capability_ids=capability_ids,
    )
    try:
        raw = await _call_contextual_recovery_model(
            payload=payload, api_key=api_key, model=model, timeout_seconds=timeout_seconds
        )
    except Exception:
        return ContextualRecoveryResult(validation_error='model_failure')
    return parse_contextual_recovery_result(raw)


async def _call_contextual_recovery_model(
    *,
    payload: dict[str, Any],
    api_key: str,
    model: str,
    timeout_seconds: float,
) -> str:
    """Make one bounded classification call; Python validates every returned ID."""
    client = AsyncOpenAI(api_key=api_key)
    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={'type': 'json_object'},
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'You are a bounded OfficeFlow/FakturaBot contextual recovery classifier. '
                        'Return JSON only with exactly recovery_outcome, failure_cause, action_id, '
                        'candidate_action_ids, capability_id, object_domain, operation, '
                        'refers_to_active_flow, confidence, and needs_clarification. Select only from Python-provided allowed outcomes, canonical '
                        'action IDs, capability IDs, domains, and operations. Never answer the user, '
                        'execute an action, request a tool, invent an ID, or claim Product Truth. '
                        'Use recent_turns only to resolve references in current_input. An active FSM '
                        'descriptor owns the conversation: prefer describe_active_flow or '
                        'describe_expected_input when the input refers to that flow. Return '
                        'genuinely_unclear when no provided bound safely fits.'
                    ),
                },
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
            ],
        ),
        timeout=timeout_seconds,
    )
    return response.choices[0].message.content or '{}'


def _workspace_key(value: str | int | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
