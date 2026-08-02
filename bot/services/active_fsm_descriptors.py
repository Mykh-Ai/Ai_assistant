from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


@dataclass(frozen=True)
class ActiveFsmDescriptor:
    action_id: str
    action_label_sk: str
    step_label_sk: str
    expected_input_kind: str
    expected_input_sk: str
    allowed_controls: tuple[str, ...] = ('/cancel', '/menu', '/start', '/issue')


_DESCRIPTORS = {
    'InvoiceStates:waiting_service_clarification': ActiveFsmDescriptor(
        'create_invoice', 'Vytvorenie faktúry', 'spresnenie služby',
        'service_description', 'stručný opis služby alebo práce',
    ),
    'InvoiceStates:waiting_slot_clarification': ActiveFsmDescriptor(
        'create_invoice', 'Vytvorenie faktúry', 'doplnenie chýbajúceho údaja',
        'state_owned_value', 'údaj vyžiadaný v poslednej správe bota',
    ),
    'InvoiceReferenceContinuationStates:waiting_reference': ActiveFsmDescriptor(
        'invoice_reference_action', 'Práca s existujúcou faktúrou', 'výber faktúry',
        'invoice_reference', 'číslo alebo jednoznačný suffix faktúry',
    ),
    'InvoiceStates:waiting_delete_existing_invoice_confirm': ActiveFsmDescriptor(
        'delete_existing_invoice', 'Vymazanie faktúry', 'potvrdenie vymazania',
        'yes_no', 'jednoznačné potvrdenie alebo zrušenie',
    ),
    'InvoiceStates:waiting_mark_existing_invoice_paid_confirm': ActiveFsmDescriptor(
        'mark_existing_invoice_paid', 'Označenie faktúry ako uhradenej', 'potvrdenie zmeny',
        'yes_no', 'jednoznačné potvrdenie alebo návrat do menu',
    ),
}

_PENDING_ACTION_LABELS = {
    'show_existing_invoice': 'Zobrazenie existujúcej faktúry',
    'edit_existing_invoice': 'Úprava existujúcej faktúry',
    'delete_existing_invoice': 'Vymazanie existujúcej faktúry',
    'mark_existing_invoice_paid': 'Označenie faktúry ako uhradenej',
}


def get_active_fsm_descriptor(
    current_state: str,
    state_data: Mapping[str, object] | None = None,
) -> ActiveFsmDescriptor:
    descriptor = _DESCRIPTORS.get(current_state)
    if descriptor is None:
        return ActiveFsmDescriptor(
            'active_business_flow', 'Rozpracovaná biznis akcia', 'zadanie údaja',
            'state_owned_value', 'hodnotu vyžiadanú v poslednej správe bota',
        )
    if current_state == 'InvoiceReferenceContinuationStates:waiting_reference':
        pending = str((state_data or {}).get('pending_invoice_reference_action') or '')
        label = _PENDING_ACTION_LABELS.get(pending)
        if label:
            return ActiveFsmDescriptor(
                pending, label, descriptor.step_label_sk,
                descriptor.expected_input_kind, descriptor.expected_input_sk,
                descriptor.allowed_controls,
            )
    return descriptor


def active_fsm_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='Hlavné menu')]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def render_active_fsm_description(descriptor: ActiveFsmDescriptor) -> str:
    return (
        f'Aktívna akcia: {descriptor.action_label_sk}.\n'
        f'Aktuálny krok: {descriptor.step_label_sk}.\n'
        f'Teraz očakávam: {descriptor.expected_input_sk}. '
        'Ak nechcete pokračovať, použite /cancel alebo Hlavné menu.'
    )


def render_active_expected_input(descriptor: ActiveFsmDescriptor) -> str:
    return (
        f'Teraz očakávam {descriptor.expected_input_sk}.\n'
        f'Pokračujete v akcii: {descriptor.action_label_sk}. '
        'Ak nechcete pokračovať, použite /cancel alebo Hlavné menu.'
    )
