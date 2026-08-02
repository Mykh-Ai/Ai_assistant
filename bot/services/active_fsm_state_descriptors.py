from __future__ import annotations

from dataclasses import dataclass, replace

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass(frozen=True)
class ActiveFsmStateDescriptor:
    action_id: str
    action_label_sk: str
    step: str
    expected_input: str
    expected_input_kind: str
    allowed_navigation: tuple[str, ...] = (
        'cancel_current_flow', 'show_main_menu', 'resume_start_status'
    )
    state_name: str | None = None

    def to_prompt_dict(self) -> dict[str, object]:
        return {
            'action_id': self.action_id,
            'action_label_sk': self.action_label_sk,
            'step': self.step,
            'expected_input': self.expected_input,
            'expected_input_kind': self.expected_input_kind,
            'allowed_navigation': list(self.allowed_navigation),
            'state_name': self.state_name,
        }


_FLOW_DESCRIPTORS: dict[str, ActiveFsmStateDescriptor] = {
    'InvoiceStates': ActiveFsmStateDescriptor(
        'create_invoice', 'vytvorenie alebo správa faktúry', 'rozpracovaný krok faktúry',
        'Pokračujte údajom, ktorý si vypýtal aktuálny krok faktúry.', 'text'
    ),
    'CustomizationRequestStates': ActiveFsmStateDescriptor(
        'customization_request', 'návrh požiadavky na úpravu', 'kontrola návrhu požiadavky',
        'Schváľte, upravte alebo zrušte zobrazený návrh.', 'decision'
    ),
    'ContactStates': ActiveFsmStateDescriptor(
        'add_contact', 'pridanie kontaktu', 'dopĺňanie kontaktu',
        'Zadajte požadovaný údaj kontaktu v textovej podobe.', 'text'
    ),
    'AccountingDocumentIntakeStates': ActiveFsmStateDescriptor(
        'add_receipt', 'spracovanie účtovného dokladu', 'kontrola alebo doplnenie dokladu',
        'Pošlite požadovaný súbor, údaj alebo vyberte ponúknutú možnosť.', 'file_or_choice'
    ),
    'OfficeFlowAttachmentRouterStates': ActiveFsmStateDescriptor(
        'officeflow_attachment_router', 'zaradenie prílohy', 'výber správneho spracovania',
        'Vyberte, čo príloha predstavuje, alebo akciu zrušte.', 'choice'
    ),
    'OnboardingStates': ActiveFsmStateDescriptor(
        'supplier_profile', 'nastavenie profilu dodávateľa', 'dopĺňanie profilu',
        'Zadajte požadovaný údaj presne v textovej podobe.', 'text'
    ),
    'SupplierProfileEditStates': ActiveFsmStateDescriptor(
        'edit_supplier', 'úprava profilu dodávateľa', 'výber alebo potvrdenie zmeny',
        'Vyberte pole, zadajte jeho novú hodnotu alebo potvrďte zmenu.', 'text_or_decision'
    ),
    'ServiceAliasStates': ActiveFsmStateDescriptor(
        'add_service_alias', 'pridanie skratky služby', 'dopĺňanie názvu služby',
        'Zadajte presný textový názov alebo skratku služby.', 'text'
    ),
    'DeleteUserDatabaseStates': ActiveFsmStateDescriptor(
        'delete_user_database', 'vymazanie používateľskej databázy', 'presné deštruktívne potvrdenie',
        'Zadajte presný text, ktorý je uvedený v potvrdení. Hlas sa nepoužíva.', 'exact_text'
    ),
    'WorkTimeStates': ActiveFsmStateDescriptor(
        'work_time', 'evidencia pracovného času', 'rozpracovaný krok dochádzky',
        'Zadajte požadovaný dátum alebo čas, prípadne vyberte ponúknutú možnosť.', 'text_or_choice'
    ),
    'BusinessProfileStates': ActiveFsmStateDescriptor(
        'switch_business_profile', 'prepnutie firemného profilu', 'výber alebo potvrdenie profilu',
        'Vyberte firemný profil alebo potvrďte jeho prepnutie.', 'choice_or_decision'
    ),
    'CustomizationRequestAdminResponseStates': ActiveFsmStateDescriptor(
        'admin_customization_review', 'odpoveď na požiadavku používateľa', 'príprava alebo potvrdenie odpovede',
        'Zadajte text odpovede alebo potvrďte jej odoslanie.', 'text_or_decision'
    ),
}

_STATE_OVERRIDES: dict[str, dict[str, str]] = {
    'InvoiceStates:waiting_input': {
        'step': 'zadanie podkladov faktúry',
        'expected_input': 'Napíšte zákazníka, položku alebo službu a cenu faktúry.',
        'expected_input_kind': 'text',
    },
    'InvoiceStates:waiting_confirm': {
        'step': 'kontrola návrhu faktúry',
        'expected_input': 'Schváľte, upravte alebo zrušte zobrazený návrh.',
        'expected_input_kind': 'decision',
    },
    'WorkTimeStates:waiting_close_input': {
        'step': 'zadanie času ukončenia práce',
        'expected_input': 'Zadajte čas ukončenia práce, napríklad 16:30.',
        'expected_input_kind': 'text',
    },
}


def describe_active_fsm_state(current_state: str) -> ActiveFsmStateDescriptor:
    state_name = str(current_state or '').strip()
    prefix = state_name.split(':', 1)[0]
    base = _FLOW_DESCRIPTORS.get(prefix)
    if base is None:
        return ActiveFsmStateDescriptor(
            action_id='unknown_active_flow',
            action_label_sk='rozpracovaná akcia',
            step='aktuálny krok',
            expected_input='Pokračujte vstupom, ktorý si vypýtal aktuálny krok, alebo použite Hlavné menu.',
            expected_input_kind='unknown',
            state_name=state_name or None,
        )
    override = _STATE_OVERRIDES.get(state_name, {})
    return replace(base, state_name=state_name, **override)


def render_active_fsm_help(
    current_state: str, *, expected_only: bool = False
) -> tuple[str, InlineKeyboardMarkup]:
    descriptor = describe_active_fsm_state(current_state)
    if expected_only:
        text = descriptor.expected_input
    else:
        text = (
            f'Teraz vykonávate: {descriptor.action_label_sk}.\n'
            f'Aktuálny krok: {descriptor.step}.\n'
            f'{descriptor.expected_input}'
        )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Hlavné menu', callback_data='navigation:show_main_menu')
    ]])
    return text, keyboard


def all_registered_state_prefixes() -> set[str]:
    return set(_FLOW_DESCRIPTORS)
