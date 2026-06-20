from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping


class ProductTruthStatus(StrEnum):
    SUPPORTED = 'supported'
    PARTIAL = 'partial'
    PLANNED = 'planned'
    UNSUPPORTED = 'unsupported'
    UNKNOWN = 'unknown'


class AccountTruthStatus(StrEnum):
    READY = 'ready'
    REQUIRES_SETUP = 'requires_setup'
    REQUIRES_ADMIN = 'requires_admin'
    REQUIRES_EXTERNAL_CREDENTIALS = 'requires_external_credentials'
    UNKNOWN = 'unknown'


@dataclass(frozen=True)
class ProductTruthCapability:
    capability_id: str
    title: str
    domain: str
    status: ProductTruthStatus
    summary_for_user: str
    current_limitations: tuple[str, ...]
    runtime_owner: str | None
    commands: tuple[str, ...]
    canonical_actions: tuple[str, ...]
    linked_handlers: tuple[str, ...]
    truth_source_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    safe_next_steps: tuple[str, ...]
    customization_allowed: bool
    dangerous: bool
    requires_setup: bool
    requires_admin: bool
    requires_external_credentials: bool
    setup_state_keys: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    last_verified_at: str
    notes_for_agents: str

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['status'] = self.status.value
        return payload


@dataclass(frozen=True)
class ProductTruthResult:
    capability: ProductTruthCapability
    product_status: ProductTruthStatus
    account_status: AccountTruthStatus
    account_requires_setup: bool
    account_requires_admin: bool
    account_requires_external_credentials: bool
    missing_setup_keys: tuple[str, ...]
    missing_external_credential_keys: tuple[str, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            'capability': self.capability.to_payload(),
            'product_status': self.product_status.value,
            'account_status': self.account_status.value,
            'account_requires_setup': self.account_requires_setup,
            'account_requires_admin': self.account_requires_admin,
            'account_requires_external_credentials': self.account_requires_external_credentials,
            'missing_setup_keys': list(self.missing_setup_keys),
            'missing_external_credential_keys': list(self.missing_external_credential_keys),
            'safe_answer_payload': {
                'capability_id': self.capability.capability_id,
                'title': self.capability.title,
                'domain': self.capability.domain,
                'product_status': self.product_status.value,
                'account_status': self.account_status.value,
                'summary_for_user': self.capability.summary_for_user,
                'current_limitations': list(self.capability.current_limitations),
                'safe_next_steps': list(self.capability.safe_next_steps),
                'customization_allowed': self.capability.customization_allowed,
                'dangerous': self.capability.dangerous,
                'requires_setup': self.capability.requires_setup or self.account_requires_setup,
                'requires_admin': self.capability.requires_admin or self.account_requires_admin,
                'requires_external_credentials': (
                    self.capability.requires_external_credentials
                    or self.account_requires_external_credentials
                ),
                'missing_setup_keys': list(self.missing_setup_keys),
                'forbidden_claims': list(self.capability.forbidden_claims),
            },
        }


_LAST_VERIFIED_AT = '2026-06-20'


def _capability(
    *,
    capability_id: str,
    title: str,
    domain: str,
    status: ProductTruthStatus,
    summary_for_user: str,
    current_limitations: tuple[str, ...] = (),
    runtime_owner: str | None = None,
    commands: tuple[str, ...] = (),
    canonical_actions: tuple[str, ...] = (),
    linked_handlers: tuple[str, ...] = (),
    truth_source_refs: tuple[str, ...],
    test_refs: tuple[str, ...] = (),
    safe_next_steps: tuple[str, ...],
    customization_allowed: bool = False,
    dangerous: bool = False,
    requires_setup: bool = False,
    requires_admin: bool = False,
    requires_external_credentials: bool = False,
    setup_state_keys: tuple[str, ...] = (),
    forbidden_claims: tuple[str, ...] = (),
    notes_for_agents: str = '',
) -> ProductTruthCapability:
    return ProductTruthCapability(
        capability_id=capability_id,
        title=title,
        domain=domain,
        status=status,
        summary_for_user=summary_for_user,
        current_limitations=current_limitations,
        runtime_owner=runtime_owner,
        commands=commands,
        canonical_actions=canonical_actions,
        linked_handlers=linked_handlers,
        truth_source_refs=truth_source_refs,
        test_refs=test_refs,
        safe_next_steps=safe_next_steps,
        customization_allowed=customization_allowed,
        dangerous=dangerous,
        requires_setup=requires_setup,
        requires_admin=requires_admin,
        requires_external_credentials=requires_external_credentials,
        setup_state_keys=setup_state_keys,
        forbidden_claims=forbidden_claims,
        last_verified_at=_LAST_VERIFIED_AT,
        notes_for_agents=notes_for_agents,
    )


_REGISTRY: tuple[ProductTruthCapability, ...] = (
    _capability(
        capability_id='create_invoice',
        title='Create outgoing invoice',
        domain='invoices',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Creates an outgoing invoice draft from text or voice, validates it, asks for approval, then saves and generates a PDF.',
        current_limitations=(
            'Requires authorized user, supplier profile, at least one service alias, and contact data for normal use.',
            'Exact identifiers, invoice numbers, dates, quantities, prices, IBAN, tax IDs, email, and final descriptions remain text-first where precision matters.',
        ),
        runtime_owner='bot/handlers/invoice.py::process_invoice_text',
        commands=('/invoice',),
        canonical_actions=('create_invoice',),
        linked_handlers=('bot/handlers/invoice.py',),
        truth_source_refs=(
            'docs/llm/Canonical_Action_Registry.md',
            'docs/FakturaBot_LLM_Orchestrator_Contract.md',
            'docs/TZ_FakturaBot.md',
            'PROJECT_LOG.md',
        ),
        test_refs=(
            'tests/test_invoice_intent_prerouter.py',
            'tests/test_invoice_state_decisions.py',
            'tests/test_voice_state_routing.py',
        ),
        safe_next_steps=('Start invoice creation through the existing /invoice flow or semantic create_invoice route.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile', 'service_alias', 'contact'),
        notes_for_agents='Supported runtime action, but setup state can make it unavailable for a specific account.',
    ),
    _capability(
        capability_id='show_existing_invoice',
        title='Show existing invoice',
        domain='invoices',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Shows one already created outgoing invoice by supplier-scoped invoice number or reference.',
        current_limitations=('Read-only; it must not enter edit mode or mutate invoice data.',),
        runtime_owner='bot/handlers/invoice.py::process_invoice_text',
        canonical_actions=('show_existing_invoice',),
        linked_handlers=('bot/handlers/invoice.py',),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/TZ_FakturaBot.md'),
        test_refs=('tests/test_invoice_intent_prerouter.py', 'tests/test_voice_state_routing.py'),
        safe_next_steps=('Ask for the invoice number or reference, then use the existing read-only view route.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='invoice_period_summary',
        title='Invoice analytics yearly fast path',
        domain='invoices',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='The invoice analytics route uses an internal deterministic read-only fast path for simple calendar-year count and total questions over saved outgoing invoices.',
        current_limitations=(
            'Supported period parsing is limited to current year, previous year, or an explicit calendar year such as 2026.',
            'This is not a competing top-level user-facing action; user-facing invoice reporting should route through invoice_analytics.',
            'It counts only already saved outgoing invoices in the current supplier scope by issue_date; it does not summarize receipts, expenses, incoming invoices, bank movements, VAT, tax, unpaid status, or arbitrary accounting analytics.',
        ),
        runtime_owner='bot/handlers/invoice.py::_run_invoice_yearly_summary_fast_path',
        canonical_actions=('invoice_analytics',),
        linked_handlers=('bot/handlers/invoice.py', 'bot/services/invoice_service.py'),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/TZ_FakturaBot.md', 'PROJECT_LOG.md'),
        test_refs=('tests/test_invoice_intent_prerouter.py', 'tests/test_info_help.py', 'tests/test_voice_state_routing.py'),
        safe_next_steps=('Ask for a yearly invoice summary, for example: Na akú sumu som vystavil faktúry tento rok?',),
        requires_setup=True,
        setup_state_keys=('authorized_user',),
        forbidden_claims=(
            'I counted receipts or incoming invoices.',
            'I counted expenses from receipts.',
            'I changed invoice data while calculating the summary.',
            'I can produce arbitrary accounting analytics from this action.',
        ),
        notes_for_agents='Internal deterministic strategy under invoice_analytics. Do not expose invoice_period_summary as a competing top-level resolver action.',
    ),
    _capability(
        capability_id='invoice_analytics',
        title='Invoice Analytics Runtime Pilot',
        domain='invoices',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Runs read-only natural-language analytics over already saved outgoing invoices for the current supplier.',
        current_limitations=(
            'Pilot scope is outgoing invoices only, current supplier only, and read-only.',
            'It can answer bounded analytical questions such as counts, sums, lists, period comparisons, grouping by customer, normalized bot payment status, or currency, and simple averages.',
            'Payment status means the bot stored/derived state from invoice follow-up data and due date, not bank-confirmed settlement.',
            'Final user-facing business answers are Slovak by default; planner answer_language metadata must not override that policy.',
            'It does not analyze receipts, incoming invoices, bank movements, tax advice, or arbitrary accounting conclusions.',
            'It must not change invoice status, edit/delete/send invoices, generate PDFs, browse files, execute SQL, or read cross-tenant data.',
            'Receipt/expense/incoming-invoice/bank/cashflow/VAT/tax wording is guarded before calculation and must not be answered from outgoing invoice data.',
        ),
        runtime_owner='bot/handlers/invoice.py::_run_invoice_analytics',
        canonical_actions=('invoice_analytics',),
        linked_handlers=(
            'bot/handlers/invoice.py',
            'bot/services/invoice_analytics_dataset.py',
            'bot/services/invoice_analytics_planner.py',
            'bot/services/safe_python_analytics_executor.py',
            'bot/services/invoice_analytics_answerer.py',
        ),
        truth_source_refs=(
            'docs/llm/Safe_Data_Analyst_Runtime_Checklist.md',
            'docs/llm/Invoice_Analytics_Runtime_Contract.md',
            'docs/llm/Canonical_Action_Registry.md',
            'docs/FakturaBot_LLM_Orchestrator_Contract.md',
            'PROJECT_LOG.md',
        ),
        test_refs=(
            'tests/test_invoice_analytics_dataset.py',
            'tests/test_invoice_analytics_planner.py',
            'tests/test_invoice_analytics_answerer.py',
            'tests/test_safe_python_analytics_executor.py',
            'tests/test_invoice_intent_prerouter.py',
            'tests/test_voice_state_routing.py',
        ),
        safe_next_steps=(
            'Ask a read-only question about saved outgoing invoices, for example: Pokaž faktúry za máj or Top klientov podľa sumy faktúr.',
        ),
        customization_allowed=True,
        requires_setup=True,
        setup_state_keys=('authorized_user',),
        forbidden_claims=(
            'I analyzed receipts or incoming invoices.',
            'I analyzed expenses from receipts using outgoing invoice data.',
            'I changed invoice status or edited invoices from analytics.',
            'I answered invoice analytics in Ukrainian because the user wrote Ukrainian.',
            'I executed SQL generated by the model.',
            'I read another supplier account.',
            'This is full accounting analytics.',
            'I gave tax or legal accounting advice.',
        ),
        notes_for_agents='Partial read-only pilot. Python owns tenant-scoped dataset construction, planner bounds, AST validation, sandboxed execution, and final response grounding.',
    ),
    _capability(
        capability_id='invoice_due_date_reminders',
        title='Invoice due-date reminders',
        domain='reminders',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Automatically checks overdue outgoing invoices for authorized suppliers, sends Telegram reminder cards, and stores the selected follow-up state.',
        current_limitations=(
            'Phase 1 uses an in-process aiogram background scheduler with a default daily check; it is not a separate external cron/worker deployment.',
            'Reminder decisions are limited to mark paid, remind later, or do not remind again.',
            'No email, SMS, accounting export, bank matching, or real Google Drive archive/upload is performed.',
        ),
        runtime_owner='bot/services/invoice_followup_scheduler.py::run_invoice_followup_scheduler and bot/services/invoice_followup_service.py',
        linked_handlers=('bot/handlers/invoice_followup.py', 'bot/services/invoice_followup_scheduler.py', 'bot/services/invoice_followup_service.py'),
        truth_source_refs=('docs/Google_Drive_Invoice_Archive_After_Due_Date_Spec.md', 'docs/TZ_FakturaBot.md', 'PROJECT_LOG.md'),
        test_refs=('tests/test_invoice_followup_service.py', 'tests/test_invoice_followup_handler.py', 'tests/test_product_truth.py', 'tests/test_info_help.py'),
        safe_next_steps=('Wait for the automatic Telegram follow-up card, then choose mark paid, remind later, or do not remind again.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
        forbidden_claims=(
            'Overdue invoice reminders use email or SMS.',
            'I sent an email or SMS reminder.',
            'I checked another supplier account.',
            'I archived the invoice to Google Drive.',
        ),
        notes_for_agents='Partial automatic in-process Telegram reminder slice. Default check interval is 86400 seconds and can be overridden by INVOICE_FOLLOWUP_CHECK_INTERVAL_SECONDS. Missing follow-up rows mean unpaid/active for detection; successful sends set remind_after to avoid repeated notifications every scheduler tick.',
    ),
    _capability(
        capability_id='edit_existing_invoice',
        title='Edit existing invoice',
        domain='invoices',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Starts the bounded edit flow for an already persisted outgoing invoice after supplier-scoped lookup.',
        current_limitations=('Exact invoice number/reference and edited exact values are precision-sensitive.',),
        runtime_owner='bot/handlers/invoice.py::process_invoice_text',
        canonical_actions=('edit_existing_invoice',),
        linked_handlers=('bot/handlers/invoice.py',),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/FakturaBot_LLM_Orchestrator_Contract.md'),
        test_refs=('tests/test_invoice_intent_prerouter.py', 'tests/test_invoice_state_decisions.py'),
        safe_next_steps=('Ask for a specific invoice reference and continue through the bounded existing-invoice edit FSM.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='delete_existing_invoice',
        title='Delete existing invoice',
        domain='invoices',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Deletes one persisted outgoing invoice only after supplier-scoped lookup and explicit confirmation.',
        current_limitations=('Voice may start the flow, but deletion is confirmation-gated and Python-owned.',),
        runtime_owner='bot/handlers/invoice.py::process_invoice_text',
        canonical_actions=('delete_existing_invoice',),
        linked_handlers=('bot/handlers/invoice.py',),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/Canonical_Decision_Resolver_Contract.md'),
        test_refs=('tests/test_invoice_intent_prerouter.py', 'tests/test_invoice_state_decisions.py'),
        safe_next_steps=('Require supplier-scoped invoice lookup and shared DecisionResolver yes/no confirmation before deletion.',),
        dangerous=True,
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
        forbidden_claims=('I deleted the invoice without confirmation.',),
    ),
    _capability(
        capability_id='invoice_pdf_generation',
        title='Invoice PDF generation',
        domain='invoice_pdf',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Generates invoice PDFs with the current FakturaBot layout and Pay by Square QR support.',
        current_limitations=('Custom customer-specific templates are not part of this capability.',),
        runtime_owner='bot/services/pdf_generator.py',
        linked_handlers=('bot/services/pdf_generator.py',),
        truth_source_refs=('docs/TZ_FakturaBot.md', 'docs/FakturaBot_PDF_Layout_Spec.md'),
        test_refs=('tests/test_pdf_generator_pay_by_square.py', 'tests/test_pdf_generator_layout_wrapping.py'),
        safe_next_steps=('Use the approved invoice flow; PDF generation happens only after Python validation and approval.',),
    ),
    _capability(
        capability_id='invoice_pdf_custom_template',
        title='Custom invoice PDF template',
        domain='invoice_pdf',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='A custom old/customer PDF template is not available in the current runtime.',
        current_limitations=('Current PDFs use the built-in FakturaBot layout.',),
        truth_source_refs=('docs/Product_Truth_Layer.md', 'docs/Info_Help_Guidance_Layer.md'),
        safe_next_steps=('Do not claim this is available; future request capture requires the Customization Request Layer.',),
        customization_allowed=True,
        forbidden_claims=('I can use your old PDF template now.', 'Your custom invoice template is already active.'),
    ),
    _capability(
        capability_id='send_invoice_email',
        title='Send invoice by email',
        domain='email',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='Real outbound invoice email sending is not implemented in the current runtime.',
        current_limitations=('Supplier/contact email fields may exist, but no supported outbound delivery flow exists.',),
        truth_source_refs=('docs/TZ_FakturaBot.md', 'docs/llm/Canonical_Action_Registry.md', 'README.md'),
        safe_next_steps=('Do not send or claim email delivery; future implementation needs provider credentials, setup, tests, and approval.',),
        customization_allowed=True,
        requires_external_credentials=True,
        forbidden_claims=('I can send invoices by email.', 'I emailed the invoice.', 'Email delivery is configured.'),
    ),
    _capability(
        capability_id='google_drive_invoice_storage',
        title='Google Drive invoice storage',
        domain='google_drive',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='Google Drive invoice storage is not implemented in the current runtime.',
        current_limitations=('Invoices are stored in the bot system and exposed through existing Telegram flows where implemented.',),
        truth_source_refs=('docs/Product_Truth_Layer.md', 'docs/TZ_FakturaBot.md', 'README.md'),
        safe_next_steps=('Do not claim Drive sync/storage; future work needs external credentials and explicit integration scope.',),
        customization_allowed=True,
        requires_external_credentials=True,
        forbidden_claims=('I can store invoices on Google Drive.', 'Google Drive sync is active.', 'I saved this invoice to Drive.'),
    ),
    _capability(
        capability_id='google_drive_invoice_archive_after_due_date',
        title='Google Drive invoice archive after due date',
        domain='google_drive',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='Real Google Drive invoice archive/upload after due-date follow-up is not implemented.',
        current_limitations=(
            'Phase 1 has only a deterministic local stub after marking an invoice as paid.',
            'The stub records that no upload happened and tells the user the invoice remains stored locally.',
            'No OAuth upload worker, Drive folder creation, file upload, local PDF deletion, or archive retry exists for this flow.',
        ),
        truth_source_refs=(
            'docs/Google_Drive_Invoice_Archive_After_Due_Date_Spec.md',
            'docs/Google_Drive_Token_Crypto_Operations.md',
            'docs/Product_Truth_Layer.md',
        ),
        safe_next_steps=('Do not claim Drive upload/archive; keep local PDF behavior and show the stub limitation only.',),
        customization_allowed=True,
        requires_external_credentials=True,
        forbidden_claims=(
            'I archived this invoice to Google Drive.',
            'The invoice was uploaded to Drive.',
            'Drive archive runs automatically after payment.',
            'Local PDFs are deleted after Drive archive.',
        ),
        notes_for_agents='Unsupported real integration; the implemented stub is not an upload/archive runtime.',
    ),
    _capability(
        capability_id='sms_reminders',
        title='SMS reminders',
        domain='sms',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='SMS reminders are not implemented in the current runtime.',
        current_limitations=('No SMS provider, consent model, phone-number workflow, or reminder scheduler is implemented.',),
        truth_source_refs=('docs/Product_Truth_Layer.md', 'docs/Info_Help_Guidance_Layer.md'),
        safe_next_steps=('Do not claim SMS sending; future work needs provider, consent, cost, and delivery rules.',),
        customization_allowed=True,
        requires_external_credentials=True,
        forbidden_claims=('I can send SMS reminders.', 'SMS reminders are active.', 'I sent an SMS.'),
    ),
    _capability(
        capability_id='accounting_export',
        title='Accounting software export',
        domain='accounting_export',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='Accounting software export is not implemented in the current runtime.',
        current_limitations=('Current accounting document support is limited to confirmed receipt/incoming-invoice intake and recent-document view where implemented.',),
        truth_source_refs=('docs/Product_Truth_Layer.md', 'docs/TZ_FakturaBot.md'),
        safe_next_steps=('Do not claim export; future work needs target software, credentials/API or file format, tests, and approval.',),
        customization_allowed=True,
        requires_external_credentials=True,
        forbidden_claims=('I can export to your accounting software.', 'I changed your accounting export.', 'Accounting export is configured.'),
    ),
    _capability(
        capability_id='bank_cashflow_tax_analytics',
        title='Bank, cashflow, VAT and tax analytics',
        domain='business_analytics',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='Bank movement, cashflow, VAT, tax, and full accounting analytics are not implemented in the current runtime.',
        current_limitations=(
            'The current analytics pilot covers only saved outgoing invoices for the current supplier.',
            'There is no bank statement intake, bank reconciliation, cashflow model, VAT report, tax advice engine, or full accounting analytics runtime.',
            'The bot must not infer tax deductibility, settlement, or accounting conclusions from invoice or receipt text.',
        ),
        truth_source_refs=(
            'docs/Product_Truth_Layer.md',
            'docs/Info_Help_Guidance_Layer.md',
            'docs/llm/Safe_Data_Analyst_Runtime_Checklist.md',
            'docs/TZ_FakturaBot.md',
        ),
        test_refs=('tests/test_product_truth.py', 'tests/test_info_help.py'),
        safe_next_steps=('Do not claim bank/cashflow/tax analytics; future work needs separate data sources, validation, Product Truth, tests, and approval.',),
        customization_allowed=True,
        forbidden_claims=(
            'I analyzed bank movements.',
            'I calculated cashflow from bank data.',
            'I produced a VAT or tax report.',
            'This is full accounting analytics.',
            'This is tax advice.',
        ),
    ),
    _capability(
        capability_id='supplier_profile',
        title='Supplier profile',
        domain='supplier_profile',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Creates or shows the supplier/company profile used on invoices.',
        current_limitations=('Unknown or unauthorized users cannot create supplier profiles.',),
        runtime_owner='bot/handlers/onboarding.py and bot/handlers/start.py',
        commands=('/moj_profil',),
        canonical_actions=('show_supplier_profile',),
        linked_handlers=('bot/handlers/onboarding.py', 'bot/handlers/start.py'),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/TZ_FakturaBot.md'),
        test_refs=('tests/test_onboarding_decisions.py', 'tests/test_voice_state_routing.py'),
        safe_next_steps=('Use /moj_profil after authorization.',),
        requires_setup=True,
        setup_state_keys=('authorized_user',),
    ),
    _capability(
        capability_id='edit_supplier_profile',
        title='Edit supplier profile',
        domain='supplier_profile',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Edits one supplier/company profile field at a time through Python validation and confirmation.',
        current_limitations=('Exact values such as IBAN, tax IDs, and email remain text-first.',),
        runtime_owner='bot/handlers/onboarding.py::cmd_upravit_profil',
        commands=('/upravit_profil',),
        canonical_actions=('edit_supplier',),
        linked_handlers=('bot/handlers/onboarding.py',),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/Canonical_Decision_Resolver_Contract.md'),
        test_refs=('tests/test_onboarding_decisions.py', 'tests/test_voice_state_routing.py'),
        safe_next_steps=('Use /upravit_profil or the bounded edit_supplier route after authorization.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='contacts',
        title='Contacts',
        domain='contacts',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Supports manual contacts and bounded AI-assisted contact intake with validation and confirmation.',
        current_limitations=('No automatic contact creation from receipts, incoming invoices, idle photos, or arbitrary attachments.',),
        runtime_owner='bot/handlers/contacts.py',
        commands=('/contact', '/contact_add'),
        canonical_actions=('add_contact',),
        linked_handlers=('bot/handlers/contacts.py',),
        truth_source_refs=('docs/TZ_FakturaBot.md', 'docs/Product_Truth_Layer.md'),
        test_refs=('tests/test_contact_intake_semantic_flow.py', 'tests/test_contact_lookup_normalization.py'),
        safe_next_steps=('Use the existing contact flow and require confirmation before saving.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='service_aliases',
        title='Service aliases',
        domain='service_aliases',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Stores supplier-owned reusable service/item naming mappings for invoice line items and PDF labels.',
        current_limitations=('Exact alias and display-name values are text-only precision steps.',),
        runtime_owner='bot/handlers/supplier.py',
        commands=('/sluzbu', '/service', '/alias'),
        canonical_actions=('add_service_alias',),
        linked_handlers=('bot/handlers/supplier.py',),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/TZ_FakturaBot.md'),
        test_refs=('tests/test_service_alias_flow.py', 'tests/test_service_alias_service.py'),
        safe_next_steps=('Use /sluzbu or the bounded add_service_alias route after supplier setup.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='add_receipt_or_incoming_invoice',
        title='Add receipt or incoming invoice',
        domain='accounting_documents',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Starts accounting document intake for receipts and incoming invoices, proposes bounded metadata and category candidates, then saves only after user approval.',
        current_limitations=(
            'Upload requires photo/PDF; broader document intake remains planned.',
            'Category changes update only the preview until the final save confirmation.',
            'Category support is controlled by the separate accounting_document_categories partial capability.',
        ),
        runtime_owner='bot/handlers/accounting_document_intake.py',
        commands=('/add_blocek', '/dodat_blocek'),
        canonical_actions=('add_receipt',),
        linked_handlers=('bot/handlers/accounting_document_intake.py',),
        truth_source_refs=('docs/TZ_FakturaBot.md', 'docs/llm/Canonical_Action_Registry.md', 'docs/llm/In_Action_Response_Registry.md'),
        test_refs=('tests/test_accounting_document_intake_flow.py', 'tests/test_accounting_document_storage.py', 'tests/test_accounting_document_extraction.py'),
        safe_next_steps=('Ask for a photo or PDF and require preview approval before confirmed save.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='accounting_document_categories',
        title='Receipt and incoming-invoice categories',
        domain='accounting_documents',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Receipts and incoming invoices can receive a controlled document category and optional line-item categories during the existing document intake preview.',
        current_limitations=(
            'This is not a top-level action; it is available only inside the existing accounting document intake preview.',
            'The model may suggest only candidates from Python-provided allowed categories or unknown_review; Python validates, the user confirms, and Python persists.',
            'Workspace custom categories can be created only after confirmation and are scoped to the current workspace.',
            'No tax deductibility, VAT report, accounting export, spending analytics, bank matching, or category totals are implemented.',
        ),
        runtime_owner='bot/handlers/accounting_document_intake.py and bot/services/accounting_document_categories.py',
        linked_handlers=('bot/handlers/accounting_document_intake.py', 'bot/services/accounting_document_categories.py'),
        truth_source_refs=(
            'docs/TZ_FakturaBot.md',
            'docs/Document_Intake_Module_Proposal.md',
            'docs/llm/In_Action_Response_Registry.md',
            'docs/Product_Truth_Layer.md',
        ),
        test_refs=(
            'tests/test_accounting_document_categories.py',
            'tests/test_accounting_document_intake_flow.py',
            'tests/test_accounting_document_extraction.py',
            'tests/test_accounting_document_storage.py',
            'tests/test_info_help.py',
        ),
        safe_next_steps=('Use /add_blocek or /dodat_blocek, upload a receipt or incoming invoice, review the proposed category, and confirm before save.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
        forbidden_claims=(
            'I calculated tax deductibility from this category.',
            'I generated receipt analytics from categories.',
            'I exported accounting categories to an accounting system.',
            'The model saved or created a category directly.',
            'This is full accounting categorization automation.',
        ),
        notes_for_agents='Partial controlled categorization only. Do not add a top-level categorize/manage category action.',
    ),
    _capability(
        capability_id='receipt_analytics',
        title='Receipt analytics',
        domain='accounting_documents',
        status=ProductTruthStatus.PLANNED,
        summary_for_user='Receipt/blocek analytics is not implemented yet; controlled categorization is only a prerequisite data-capture layer.',
        current_limitations=(
            'The current runtime can intake, categorize, save, and show recent confirmed receipts/incoming invoices only within its implemented partial scope.',
            'There is no spending analytics runtime, category totals/reporting, incoming-invoice analytics, or evaluated accounting conclusion layer yet.',
            'Raw OCR, LMM extraction, and even confirmed intake categories must not be treated as tax deductibility or accounting approval.',
            'No broad receipt spending analytics, category totals, incoming-invoice analytics, bank matching, VAT/tax report, or full accounting analytics is implemented.',
        ),
        truth_source_refs=(
            'docs/llm/Safe_Data_Analyst_Runtime_Checklist.md',
            'docs/Product_Truth_Layer.md',
            'docs/Info_Help_Guidance_Layer.md',
            'docs/TZ_FakturaBot.md',
        ),
        test_refs=('tests/test_product_truth.py', 'tests/test_info_help.py'),
        safe_next_steps=(
            'Use controlled categories as captured metadata only; build a separate read-only analytics contract, dataset, evaluator, Product Truth, and tests before any receipt analytics runtime.',
        ),
        customization_allowed=True,
        forbidden_claims=(
            'I analyzed receipt categories.',
            'I categorized your receipts for analytics.',
            'Raw OCR is a final accounting category.',
            'I calculated tax deductibility from receipts.',
            'Receipt analytics is implemented.',
        ),
        notes_for_agents='Planned capability only. Do not route receipt analytics questions to the add/upload receipt flow.',
    ),
    _capability(
        capability_id='show_recent_accounting_documents',
        title='Show recent accounting documents',
        domain='accounting_documents',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Shows recent confirmed receipt/incoming-invoice metadata in a read-only list.',
        current_limitations=('Not a broad document browser, invoice PDF browser, search, edit, delete, or Google Drive sync.',),
        runtime_owner='bot/handlers/accounting_documents.py',
        commands=('/blocek', '/blocky'),
        canonical_actions=('show_recent_accounting_documents',),
        linked_handlers=('bot/handlers/accounting_documents.py',),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/TZ_FakturaBot.md'),
        test_refs=('tests/test_accounting_documents_handler.py', 'tests/test_accounting_document_registry.py'),
        safe_next_steps=('Use /blocek for the current read-only recent document view.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='officeflow_idle_attachment_router',
        title='OfficeFlow idle attachment router',
        domain='officeflow_attachment_router',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Classifies idle photo/PDF attachments after authorization and proposes a bounded next step.',
        current_limitations=('Active FSM state wins; no save/create side effect happens from classification alone; standalone contract save is not implemented.',),
        runtime_owner='bot/handlers/officeflow_attachment_router.py',
        linked_handlers=('bot/handlers/officeflow_attachment_router.py',),
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/FakturaBot_LLM_Orchestrator_Contract.md'),
        test_refs=('tests/test_officeflow_attachment_router.py', 'tests/test_officeflow_attachment_classifier.py'),
        safe_next_steps=('Only propose a bounded route after authorization and require user confirmation before side effects.',),
        requires_setup=True,
        setup_state_keys=('authorized_user',),
    ),
    _capability(
        capability_id='voice_invoice_intake',
        title='Voice invoice intake',
        domain='voice',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Voice can start invoice creation and some bounded controls, then text/file is required for precision-sensitive values.',
        current_limitations=('Voice must not fill IBAN, tax IDs, email, invoice numbers, item numeric values, final descriptions, service alias names, or exact destructive confirmations.',),
        runtime_owner='bot/handlers/voice.py',
        canonical_actions=('create_invoice',),
        linked_handlers=('bot/handlers/voice.py', 'bot/handlers/invoice.py'),
        truth_source_refs=('docs/TZ_FakturaBot.md', 'docs/FakturaBot_LLM_Orchestrator_Contract.md'),
        test_refs=('tests/test_voice_state_routing.py', 'tests/test_speech_to_text.py'),
        safe_next_steps=('Use voice only for supported intent/control surfaces and switch to text/file for exact values.',),
        requires_setup=True,
        setup_state_keys=('authorized_user',),
    ),
    _capability(
        capability_id='delete_user_database',
        title='Delete user database',
        domain='access_control',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Deletes the authorized user scoped business data and removes bot access after exact typed confirmation.',
        current_limitations=('Voice may start the warning flow but cannot pass the final exact destructive confirmation.',),
        runtime_owner='bot/handlers/delete_user_database.py',
        commands=('/vymazat_databazu',),
        canonical_actions=('delete_user_database',),
        linked_handlers=('bot/handlers/delete_user_database.py',),
        truth_source_refs=('docs/TZ_FakturaBot.md', 'docs/Canonical_Decision_Resolver_Contract.md'),
        test_refs=('tests/test_delete_user_database_flow.py', 'tests/test_tenant_safety.py'),
        safe_next_steps=('Start only the warning flow, then require exact typed confirmation before deletion.',),
        dangerous=True,
        requires_setup=True,
        setup_state_keys=('authorized_user',),
        forbidden_claims=('I deleted your database without exact typed confirmation.', 'Voice confirmation deleted your database.'),
    ),
    _capability(
        capability_id='customization_requests',
        title='Customization requests',
        domain='customization',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Supports confirmation-gated capture and tenant-scoped persistence of customization or human-review requests, including admin review and answer-only response delivery.',
        current_limitations=(
            'Supported subset: user preview/edit/approve/cancel, confirmed save, admin list/detail, admin accept/reject status review, answer-only admin response-to-user, and delivery metadata/observability.',
            'No automatic implementation, Product Truth mutation, backlog conversion, code-agent handoff, self-learning, threaded conversation, auto retry, response kinds beyond answer, SLA, or guaranteed delivery.',
        ),
        runtime_owner='bot/services/customization_requests.py and bot/handlers/access_admin.py',
        commands=('/customization_requests', '/customization_request', '/customization_request_reply'),
        linked_handlers=('bot/handlers/invoice.py', 'bot/handlers/access_admin.py'),
        truth_source_refs=('docs/Customization_Request_Layer.md', 'docs/Product_Truth_Layer.md'),
        test_refs=('tests/test_customization_requests.py', 'tests/test_customization_request_admin.py'),
        safe_next_steps=('Offer request save only through the existing confirmation-gated preview flow; never imply implementation or Product Truth mutation.',),
        requires_setup=True,
        setup_state_keys=('authorized_user',),
        forbidden_claims=(
            'This feature will be implemented.',
            'Product Truth was updated.',
            'A code-agent task was created.',
            'Admin notification exists automatically.',
            'Complete Level 3 customization layer is available.',
            'You will definitely receive an answer.',
        ),
        notes_for_agents='Partial human-review loop exists. Treat accepted/rejected as review status only; admin answer delivery is latest-response metadata only.',
    ),
    _capability(
        capability_id='admin_customization_review',
        title='Admin customization request review',
        domain='customization_admin',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Admins can list/detail tenant-scoped requests and mark them reviewed_accepted or reviewed_rejected as status-only decisions.',
        current_limitations=(
            'Accept/reject does not promise implementation, send automatic user notification, mutate Product Truth, or create backlog/code-agent work.',
        ),
        runtime_owner='bot/handlers/access_admin.py',
        commands=('/customization_requests', '/customization_request'),
        linked_handlers=('bot/handlers/access_admin.py',),
        truth_source_refs=('docs/Customization_Request_Layer.md', 'docs/Product_Truth_Layer.md'),
        test_refs=('tests/test_customization_request_admin.py',),
        safe_next_steps=('Use admin status review only as review metadata; use the separate reply flow for answer delivery.',),
        requires_admin=True,
        forbidden_claims=(
            'Accepted means implemented.',
            'Rejected automatically notified the user.',
            'Admin review updated Product Truth.',
        ),
    ),
    _capability(
        capability_id='admin_response_to_user',
        title='Admin response to user',
        domain='customization_admin',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Admins can send one confirmation-gated, answer-kind response to the original requester through the bot.',
        current_limitations=(
            'MVP stores only latest response metadata, supports answer kind only, and has no threaded history, no auto retry, notification on review status, SLA, or guaranteed delivery.',
            'The LLM never sends the response directly; Python persists metadata before Telegram delivery and records send_succeeded or send_failed.',
        ),
        runtime_owner='bot/handlers/access_admin.py::cmd_customization_request_reply',
        commands=('/customization_request_reply',),
        linked_handlers=('bot/handlers/access_admin.py',),
        truth_source_refs=('docs/Customization_Request_Layer.md', 'docs/Product_Truth_Layer.md'),
        test_refs=('tests/test_customization_request_admin.py',),
        safe_next_steps=('Admin reply requires typed text, preview, and explicit send confirmation before outbound delivery.',),
        requires_admin=True,
        forbidden_claims=(
            'Admin replies are guaranteed to arrive.',
            'The bot learned this answer automatically.',
            'The answer makes the feature supported.',
        ),
    ),
    _capability(
        capability_id='admin_response_delivery_observability',
        title='Admin response delivery observability',
        domain='customization_admin',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Admin request detail shows latest response delivery metadata such as not_started, send_pending, send_succeeded, send_failed, attempts, timestamps, bounded failure reason, and a redacted preview.',
        current_limitations=(
            'Observability is admin-facing only; there is no retry command, recovery command, delivery_unknown marking, automatic recovery, or guaranteed delivery.',
        ),
        runtime_owner='bot/handlers/access_admin.py::_format_customization_request_detail',
        commands=('/customization_request',),
        linked_handlers=('bot/handlers/access_admin.py',),
        truth_source_refs=('docs/Customization_Request_Layer.md', 'docs/Product_Truth_Layer.md'),
        test_refs=('tests/test_customization_request_admin.py',),
        safe_next_steps=('Use admin detail for manual investigation of send_pending or send_failed; do not auto-resend.',),
        requires_admin=True,
        forbidden_claims=(
            'The user sees delivery internals.',
            'send_pending means delivered.',
            'send_pending means failed.',
            'The bot will retry automatically.',
        ),
    ),
    _capability(
        capability_id='access_request_approval',
        title='Access request and admin approval',
        domain='access_control',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Unknown users can request access and admins can approve or reject access before business flows are available.',
        current_limitations=(
            'Pending access requests are not tenants, supplier profiles, or business onboarding; authorization is required before business side effects.',
        ),
        runtime_owner='bot/handlers/access_admin.py and bot/services/authorization.py',
        commands=('/access_requests',),
        linked_handlers=('bot/handlers/access_admin.py', 'bot/services/authorization.py'),
        truth_source_refs=('docs/User_Access_Model_Roadmap.md', 'AGENTS.md', 'PROJECT_LOG.md'),
        test_refs=('tests/test_authorization_service.py', 'tests/test_access_request_admin.py'),
        safe_next_steps=('Unknown users must request access and wait for admin approval before supplier, invoice, contact, or document flows.',),
        requires_admin=True,
        forbidden_claims=('Pending access means business access is active.', 'Unknown users can create business data.'),
    ),
    _capability(
        capability_id='invoice_draft_edit_flow',
        title='Invoice draft edit flow',
        domain='invoices',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Before saving an invoice, the draft preview supports bounded edit/approve/cancel decisions through the shared DecisionResolver flow.',
        current_limitations=('Exact edited invoice values remain text-first and must pass Python validation before save/PDF generation.',),
        runtime_owner='bot/handlers/invoice.py',
        commands=('/invoice',),
        canonical_actions=('create_invoice',),
        linked_handlers=('bot/handlers/invoice.py',),
        truth_source_refs=('docs/Canonical_Decision_Resolver_Contract.md', 'docs/FakturaBot_LLM_Orchestrator_Contract.md'),
        test_refs=('tests/test_invoice_state_decisions.py', 'tests/test_decision_callbacks.py'),
        safe_next_steps=('Use invoice preview controls to edit the draft before approval; nothing is saved until confirmation.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile', 'service_alias', 'contact'),
    ),
    _capability(
        capability_id='code_agent_handoff',
        title='Code-agent handoff',
        domain='customization',
        status=ProductTruthStatus.UNSUPPORTED,
        summary_for_user='Bot-runtime code-agent handoff is not implemented.',
        current_limitations=('Implementation tasks still require human review and are not created by the Telegram runtime.',),
        truth_source_refs=('docs/Code_Agent_Handoff_Contract.md', 'docs/Product_Truth_Layer.md'),
        safe_next_steps=('Do not claim handoff, patch preparation, merge, or deployment from runtime chat.',),
        dangerous=True,
        requires_admin=True,
        forbidden_claims=('I handed this to a code agent.', 'I will deploy this change.', 'I merged the implementation.'),
    ),
    _capability(
        capability_id='self_learning_aliases',
        title='Confirmed semantic alias learning',
        domain='self_learning',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Stores some confirmed supplier-scoped contact and service aliases after successful/confirmed resolution.',
        current_limitations=('Not broad topic learning, not Product Truth mutation, and not an adaptive workflow engine.',),
        runtime_owner='bot/services/contact_service.py and bot/services/service_alias_service.py',
        linked_handlers=('bot/handlers/invoice.py', 'bot/services/contact_service.py', 'bot/services/service_alias_service.py'),
        truth_source_refs=('docs/Self_Learning_Layer.md', 'docs/Confirmed_Semantic_Alias_Learning_Contract.md'),
        test_refs=('tests/test_invoice_phase2_ai_layer.py', 'tests/test_service_alias_service.py', 'tests/test_contact_lookup_normalization.py'),
        safe_next_steps=('Learn only after confirmed resolution and never let aliases change Product Truth or create canonical actions.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
        forbidden_claims=('I learned a new product capability.', 'Learned aliases can enable unsupported features.'),
    ),
    _capability(
        capability_id='info_help',
        title='InfoHelp guidance',
        domain='info_help',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Current runtime has deterministic Product Truth-backed InfoHelp for selected conservative capability and safety topics, plus bounded Unknown / Discovery / Triage v1 classification.',
        current_limitations=(
            'This is a partial Level 2 foundation with deterministic fast-path and bounded triage v1, not complete arbitrary capability-aware Q&A.',
            'Full Level 2 still requires broader bounded InfoHelp resolver coverage, voice/STT parity across the full surface, multilingual and noisy-input evaluation, and account-context-aware runtime evidence.',
            'InfoHelp can describe selected human-review capabilities, but does not itself save requests, send admin responses, mutate Product Truth, or hand off code-agent work.',
        ),
        runtime_owner='bot/services/info_help.py::build_product_truth_guidance, build_info_help_triage_guidance, and build_top_level_unknown_guidance',
        linked_handlers=('bot/services/info_help.py',),
        truth_source_refs=('docs/Info_Help_Guidance_Layer.md', 'PROJECT_LOG.md'),
        test_refs=('tests/test_product_truth.py', 'tests/test_info_help.py', 'tests/test_invoice_intent_prerouter.py'),
        safe_next_steps=(
            'Use only the current conservative Product Truth fast-path for covered topics.',
            'Use bounded triage v1 only for safe classification; do not claim broad Level 2 coverage.',
        ),
        forbidden_claims=(
            'InfoHelp Level 2 is complete.',
            'I can answer any product capability question.',
            'InfoHelp saved your customization request.',
            'InfoHelp sent an admin response.',
            'InfoHelp has voice/STT parity.',
        ),
        notes_for_agents='Partial Product Truth-backed runtime and bounded triage v1 exist for selected topics/discovery classes only; do not describe InfoHelp as complete Level 2.',
    ),
)

_REGISTRY_BY_ID: dict[str, ProductTruthCapability] = {
    capability.capability_id: capability for capability in _REGISTRY
}


def list_capabilities() -> tuple[ProductTruthCapability, ...]:
    return _REGISTRY


def get_capability(
    capability_id: str,
    account_context: Mapping[str, Any] | None = None,
) -> ProductTruthResult:
    capability = _REGISTRY_BY_ID.get(capability_id, _unknown_capability(capability_id))
    return _merge_account_context(capability, account_context)


def get_safe_answer_payload(
    capability_id: str,
    account_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return get_capability(capability_id, account_context=account_context).to_payload()['safe_answer_payload']


def search_capabilities(
    query_or_topic: str,
    allowed_capability_ids: tuple[str, ...] | list[str] | None = None,
) -> tuple[ProductTruthCapability, ...]:
    query = query_or_topic.strip().lower()
    allowed = set(allowed_capability_ids or ())
    results: list[ProductTruthCapability] = []
    for capability in _REGISTRY:
        if allowed and capability.capability_id not in allowed:
            continue
        if not query or query in capability.capability_id or query in capability.domain or query in capability.title.lower():
            results.append(capability)
    return tuple(results)


def validate_registry() -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[str] = set()
    for capability in _REGISTRY:
        if capability.capability_id in seen:
            errors.append(f'duplicate capability_id: {capability.capability_id}')
        seen.add(capability.capability_id)
        if capability.status not in set(ProductTruthStatus):
            errors.append(f'{capability.capability_id}: invalid status {capability.status}')
        if capability.status == ProductTruthStatus.SUPPORTED:
            if not capability.runtime_owner:
                errors.append(f'{capability.capability_id}: supported entry missing runtime_owner')
            if not capability.truth_source_refs:
                errors.append(f'{capability.capability_id}: supported entry missing truth_source_refs')
            if not capability.test_refs:
                errors.append(f'{capability.capability_id}: supported entry missing test_refs')
        if capability.status in {ProductTruthStatus.UNSUPPORTED, ProductTruthStatus.PLANNED}:
            if capability.runtime_owner or capability.linked_handlers:
                errors.append(f'{capability.capability_id}: unsupported/planned entry claims runtime owner')
        if capability.dangerous and not capability.safe_next_steps:
            errors.append(f'{capability.capability_id}: dangerous entry missing safe_next_steps')
        if capability.requires_external_credentials and not capability.forbidden_claims:
            errors.append(f'{capability.capability_id}: external-credential entry missing forbidden_claims')
    return tuple(errors)


def _merge_account_context(
    capability: ProductTruthCapability,
    account_context: Mapping[str, Any] | None,
) -> ProductTruthResult:
    context = account_context or {}
    missing_setup = _missing_setup_keys(capability, context)
    missing_external = _missing_external_credential_keys(capability, context)
    account_requires_admin = _context_false(context, 'authorized_user') or capability.requires_admin
    account_requires_setup = bool(missing_setup)
    account_requires_external = bool(missing_external)

    account_status = AccountTruthStatus.READY
    if capability.status == ProductTruthStatus.UNKNOWN:
        account_status = AccountTruthStatus.UNKNOWN
    elif account_requires_admin:
        account_status = AccountTruthStatus.REQUIRES_ADMIN
    elif account_requires_setup:
        account_status = AccountTruthStatus.REQUIRES_SETUP
    elif account_requires_external:
        account_status = AccountTruthStatus.REQUIRES_EXTERNAL_CREDENTIALS

    return ProductTruthResult(
        capability=capability,
        product_status=capability.status,
        account_status=account_status,
        account_requires_setup=account_requires_setup,
        account_requires_admin=account_requires_admin,
        account_requires_external_credentials=account_requires_external,
        missing_setup_keys=missing_setup,
        missing_external_credential_keys=missing_external,
    )


def _missing_setup_keys(
    capability: ProductTruthCapability,
    account_context: Mapping[str, Any],
) -> tuple[str, ...]:
    if not capability.requires_setup:
        return ()
    missing: list[str] = []
    for key in capability.setup_state_keys:
        if key == 'authorized_user':
            continue
        if _context_false(account_context, key):
            missing.append(key)
    return tuple(missing)


def _missing_external_credential_keys(
    capability: ProductTruthCapability,
    account_context: Mapping[str, Any],
) -> tuple[str, ...]:
    if not capability.requires_external_credentials:
        return ()
    credential_key = f'{capability.capability_id}_credentials'
    if _context_false(account_context, credential_key):
        return (credential_key,)
    return ()


def _context_false(account_context: Mapping[str, Any], key: str) -> bool:
    return key in account_context and account_context[key] is False


def _unknown_capability(capability_id: str) -> ProductTruthCapability:
    normalized_id = capability_id.strip() or 'unknown'
    return ProductTruthCapability(
        capability_id=normalized_id,
        title='Unknown capability',
        domain='unknown',
        status=ProductTruthStatus.UNKNOWN,
        summary_for_user='Product Truth has no verified entry for this capability.',
        current_limitations=('No runtime support claim can be made without a verified registry entry.',),
        runtime_owner=None,
        commands=(),
        canonical_actions=(),
        linked_handlers=(),
        truth_source_refs=('docs/Product_Truth_Layer.md',),
        test_refs=(),
        safe_next_steps=('Return unknown, ask for clarification, or route to human/developer review.',),
        customization_allowed=False,
        dangerous=False,
        requires_setup=False,
        requires_admin=False,
        requires_external_credentials=False,
        setup_state_keys=(),
        forbidden_claims=('This unknown capability is supported.',),
        last_verified_at=_LAST_VERIFIED_AT,
        notes_for_agents='Unknown must not become action execution.',
    )


_VALIDATION_ERRORS = validate_registry()
if _VALIDATION_ERRORS:
    raise RuntimeError('Invalid Product Truth registry: ' + '; '.join(_VALIDATION_ERRORS))
