from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class InfoHelpActionSemantic:
    action_id: str
    capability_id: str
    domain_id: str
    object_kind: str
    operation_id: str
    mutation_class: str
    runtime_owner: str
    public_commands: tuple[str, ...]
    required_slots: tuple[str, ...]
    entry_mode: str
    continuation_state: str | None
    confirmation_family: str | None
    infohelp_action_button_allowed: bool
    eligibility_reason: str

    def as_safe_payload(self) -> dict[str, object]:
        value = asdict(self)
        value['runtime_owner'] = bool(self.runtime_owner)
        return value


_ACTIONS = (
    InfoHelpActionSemantic('show_existing_invoice', 'show_existing_invoice', 'invoices', 'invoice', 'show', 'read_only', 'bot.handlers.invoice::_execute_invoice_reference_action', (), ('invoice_reference',), 'continuation_fsm', 'InvoiceReferenceContinuationStates:waiting_reference', None, False, 'Requires a supplier/workspace-scoped invoice reference; continuation exists.'),
    InfoHelpActionSemantic('edit_existing_invoice', 'edit_existing_invoice', 'invoices', 'invoice', 'edit', 'mutating', 'bot.handlers.invoice::_execute_invoice_reference_action', (), ('invoice_reference',), 'continuation_fsm', 'InvoiceReferenceContinuationStates:waiting_reference', None, False, 'Starts the existing bounded edit owner after scoped lookup.'),
    InfoHelpActionSemantic('delete_existing_invoice', 'delete_existing_invoice', 'invoices', 'invoice', 'delete', 'destructive', 'bot.handlers.invoice::_execute_invoice_reference_action', (), ('invoice_reference',), 'continuation_fsm', 'InvoiceReferenceContinuationStates:waiting_reference', 'yes_no', False, 'Lookup only; the existing destructive confirmation remains mandatory.'),
    InfoHelpActionSemantic('mark_existing_invoice_paid', 'mark_existing_invoice_paid', 'invoices', 'invoice', 'mark_paid', 'mutating', 'bot.handlers.invoice::_execute_invoice_reference_action', (), ('invoice_reference',), 'continuation_fsm', 'InvoiceReferenceContinuationStates:waiting_reference', 'yes_no', False, 'Marks bot-local payment state only after existing confirmation.'),
    InfoHelpActionSemantic('show_supplier_profile', 'supplier_profile', 'supplier_profile', 'supplier_profile', 'show', 'read_only', 'bot.handlers.start::cmd_moj_profil', ('/moj_profil',), (), 'immediate_existing_owner', None, None, False, 'Existing read-only profile owner.'),
    InfoHelpActionSemantic('edit_supplier', 'edit_supplier_profile', 'supplier_profile', 'supplier_profile', 'edit', 'mutating', 'bot.handlers.onboarding::cmd_upravit_profil', ('/upravit_profil',), (), 'existing_fsm_entry', None, 'yes_no', False, 'Existing field/value/confirmation flow.'),
    InfoHelpActionSemantic('add_contact', 'contacts', 'contacts', 'contact', 'create', 'mutating', 'bot.handlers.contacts::start_add_contact_intake', ('/contact', '/contact_add', '/add_kontakt'), (), 'existing_fsm_entry', None, 'yes_no', False, 'Existing confirmation-gated contact intake.'),
    InfoHelpActionSemantic('add_receipt', 'add_receipt_or_incoming_invoice', 'accounting_documents', 'receipt', 'create', 'mutating', 'bot.handlers.accounting_document_intake::cmd_accounting_document_intake', ('/blocek',), ('attachment',), 'existing_fsm_entry', None, 'approve_edit_cancel', False, 'Existing attachment intake; no save before confirmation.'),
    InfoHelpActionSemantic('show_recent_accounting_documents', 'show_recent_accounting_documents', 'accounting_documents', 'accounting_document', 'show_recent', 'read_only', 'bot.handlers.accounting_documents::cmd_blocky', ('/blocky',), (), 'immediate_existing_owner', None, None, False, 'Existing read-only list owner.'),
    InfoHelpActionSemantic('delete_user_database', 'delete_user_database', 'access_control', 'user_data', 'delete', 'destructive', 'bot.handlers.delete_user_database::start_delete_user_database_flow', ('/vymazat_databazu',), (), 'not_infohelp_eligible', None, 'exact_typed', False, 'Account-wide deletion is never suggested by InfoHelp.'),
)

_BY_ID = {item.action_id: item for item in _ACTIONS}


def list_info_help_actions() -> tuple[InfoHelpActionSemantic, ...]:
    return _ACTIONS


def get_info_help_action(action_id: str | None) -> InfoHelpActionSemantic | None:
    return _BY_ID.get(str(action_id or ''))


def find_exact_info_help_action(
    *, domain_id: str, object_kind: str, operation_id: str
) -> InfoHelpActionSemantic | None:
    for item in _ACTIONS:
        if (item.domain_id, item.object_kind, item.operation_id) == (
            domain_id,
            object_kind,
            operation_id,
        ):
            return item
    return None


def info_help_action_payload() -> list[dict[str, object]]:
    return [item.as_safe_payload() for item in _ACTIONS]
