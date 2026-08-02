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
    supported_channels: tuple[str, ...] = ()
    unsupported_channels: tuple[str, ...] = ()

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


_LAST_VERIFIED_AT = '2026-07-01'


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
    supported_channels: tuple[str, ...] = (),
    unsupported_channels: tuple[str, ...] = (),
    last_verified_at: str = _LAST_VERIFIED_AT,
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
        last_verified_at=last_verified_at,
        notes_for_agents=notes_for_agents,
        supported_channels=supported_channels,
        unsupported_channels=unsupported_channels,
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
            'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md',
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
            'An explicitly named customer is resolved through the same tenant-scoped exact, normalized, confirmed-alias, fuzzy, then bounded-fallback chain used for invoice generation; Python prefilters by trusted contact id, asks for clarification if unresolved, and does not save an alias.',
            'Payment status means the bot stored/derived state from invoice follow-up data and due date, not bank-confirmed settlement.',
            'Unpaid/not-paid invoice questions include both pending_payment and overdue bot states; muted reminders are still unpaid until marked paid.',
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
            'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md',
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
            'No email, SMS, accounting export, or bank matching is performed. Google Drive archive is only a separate owner OAuth integration when configured.',
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
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md'),
        test_refs=('tests/test_invoice_intent_prerouter.py', 'tests/test_invoice_state_decisions.py'),
        safe_next_steps=('Ask for a specific invoice reference and continue through the bounded existing-invoice edit FSM.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),
    _capability(
        capability_id='mark_existing_invoice_paid',
        title='Mark existing invoice as paid',
        domain='invoices',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Marks one already saved outgoing invoice as paid/uhradena after supplier-scoped lookup and explicit confirmation.',
        current_limitations=(
            'This stores bot-local payment state only; it is not bank-confirmed settlement and does not match bank movements.',
            'The user must provide a concrete invoice reference and confirm the action before any state is written.',
            'When owner OAuth Google Drive mode is enabled, the action may enqueue the local PDF for Drive archive; otherwise it records only the local Drive archive stub.',
        ),
        runtime_owner='bot/handlers/invoice.py::process_invoice_text and bot/services/invoice_followup_service.py::InvoiceFollowupService.mark_paid',
        canonical_actions=('mark_existing_invoice_paid',),
        linked_handlers=('bot/handlers/invoice.py', 'bot/services/invoice_followup_service.py', 'bot/services/invoice_drive_archive_service.py', 'bot/services/google_drive_archive_stub.py'),
        truth_source_refs=(
            'docs/llm/Canonical_Action_Registry.md',
            'docs/llm/In_Action_Response_Registry.md',
            'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md',
            'docs/TZ_FakturaBot.md',
            'PROJECT_LOG.md',
        ),
        test_refs=(
            'tests/test_invoice_intent_prerouter.py',
            'tests/test_invoice_state_decisions.py',
            'tests/test_decision_callbacks.py',
            'tests/test_voice_state_routing.py',
            'tests/test_product_truth.py',
            'tests/test_info_help.py',
        ),
        safe_next_steps=('Say or type: oznac fakturu 04 ako uhradenu, then confirm with the provided button.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
        forbidden_claims=(
            'I confirmed the bank payment.',
            'I matched the invoice with bank data.',
            'I uploaded the invoice to Google Drive.',
            'I marked the invoice as paid without confirmation.',
        ),
        notes_for_agents='Supported MVP is manual confirmation-gated bot-local payment state only. Drive archive is optional owner OAuth enqueue/upload and never bank matching.',
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
        capability_id='gmail_statement_collection',
        title='Gmail bank statement collection',
        domain='gmail',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='A configured workspace can connect one verified Gmail account and collect matching bank-statement attachments into tenant-scoped local storage.',
        current_limitations=(
            'The integration is disabled by default and requires admin setup, Google OAuth client credentials, encrypted token storage, an exact target workspace and an expected Google email address.',
            'Only the restricted gmail.readonly scope is allowed; Google Drive permissions are not requested and the existing owner Drive integration remains separate.',
            'The collector accepts only bounded configured MIME types and extensions, stores originals and metadata atomically, and deduplicates by Gmail source and workspace-local content hash.',
            'Imported statements have parse_status=deferred: no bank parsing, transaction matching, cashflow, VAT, tax analysis, or accounting conclusions are implemented.',
            'The public OAuth callback and internal callback service require deployment and Google Console verification before a real account connection can be claimed.',
        ),
        commands=('gmail_connect', 'gmail_status', 'gmail_disconnect'),
        runtime_owner='bot/handlers/gmail_settings.py, bot/services/google_integration_service.py, bot/services/gmail_statement_scheduler.py and bot/services/gmail_statement_collector.py',
        linked_handlers=('bot/handlers/gmail_settings.py', 'bot/google_integration_callback_app.py'),
        truth_source_refs=(
            'docs/architecture/GOOGLE_MULTI_ACCOUNT_OAUTH_FOUNDATION_GMAIL_STATEMENT_COLLECTOR_V1_ARCHITECTURE_DESIGN_PROOF.md',
            'docs/Google_Gmail_Statement_Collector_Setup_Runbook.md',
            'docs/TZ_FakturaBot.md',
        ),
        test_refs=(
            'tests/test_google_integration_service.py',
            'tests/test_google_integration_oauth.py',
            'tests/test_google_integration_callback.py',
            'tests/test_gmail_statement_collector.py',
            'tests/test_google_gmail_config.py',
            'tests/test_gmail_statement_scheduler.py',
            'tests/test_gmail_statement_archive.py',
        ),
        safe_next_steps=('An administrator must complete the external Google setup, enable the separate Gmail flags, connect the expected account with /gmail_connect, and verify /gmail_status before collection is expected.',),
        customization_allowed=True,
        requires_setup=True,
        requires_admin=True,
        requires_external_credentials=True,
        setup_state_keys=('authorized_user', 'workspace_membership', 'google_gmail_oauth'),
        forbidden_claims=(
            'Gmail collection is enabled for every workspace.',
            'The bot can read or send all email.',
            'The Gmail integration has Google Drive access.',
            'A collected statement was parsed or reconciled.',
            'The OAuth callback is live before deployment and external verification.',
        ),
    ),
    _capability(
        capability_id='google_drive_invoice_storage',
        title='Google Drive invoice storage',
        domain='google_drive',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Owner Google Drive archive is available as a partial owner OAuth integration for a single configured owner account.',
        current_limitations=(
            'This is not per-client OAuth or SaaS Drive sync; one owner Google account authorizes once through the owner OAuth bootstrap and uploads consume the owner account quota.',
            'Outgoing invoice PDFs are only enqueued after a control event such as marking the invoice paid; generated PDFs remain stored locally in the bot.',
            'Receipts and incoming invoices can be uploaded from the confirmed archive outbox when Drive is enabled and configured.',
            'Each newly confirmed accounting document is queued under the owning workspace persisted Drive folder; upload remains asynchronous and a successful local save does not claim Drive success.',
            'Accounting metadata remains local, failed or pending uploads preserve the original, and existing remote files are not migrated automatically.',
            'Missing OAuth credentials, encrypted refresh token, root folder access, or Google API dependencies leave jobs retryable/failed without deleting local files.',
            'Service-account mode is unsupported for personal My Drive unless a future Google Workspace/Shared Drive setup is explicitly configured.',
        ),
        runtime_owner='bot/services/accounting_document_archive_path.py, bot/services/invoice_drive_archive_service.py and bot/services/google_drive_archive_scheduler.py',
        linked_handlers=('bot/handlers/invoice.py', 'bot/handlers/invoice_followup.py', 'bot/services/archive_worker.py'),
        truth_source_refs=('docs/Product_Truth_Layer.md', 'docs/TZ_FakturaBot.md', 'README.md'),
        test_refs=('tests/test_google_drive_service_account_archive.py', 'tests/test_archive_worker.py', 'tests/test_product_truth.py', 'tests/test_info_help.py'),
        safe_next_steps=('Configure GOOGLE_DRIVE_ENABLED=1, owner OAuth client credentials, GOOGLE_TOKEN_CRYPTO_SECRET, an encrypted owner refresh token, and GOOGLE_DRIVE_ROOT_FOLDER_ID before expecting uploads.',),
        customization_allowed=True,
        requires_setup=True,
        requires_admin=True,
        requires_external_credentials=True,
        setup_state_keys=('authorized_user', 'supplier_profile', 'google_drive_owner_oauth'),
        forbidden_claims=(
            'Google Drive sync is active for every user.',
            'This is per-client Google OAuth Drive storage.',
            'All business profiles share one archive folder.',
            'Existing remote accounting files were migrated automatically.',
            'A confirmed local save means the Drive upload already succeeded.',
            'Service-account mode works with personal My Drive.',
            'I deleted the local invoice PDF after upload.',
        ),
    ),
    _capability(
        capability_id='google_drive_invoice_archive_after_due_date',
        title='Google Drive invoice archive after due date',
        domain='google_drive',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='After a due-date follow-up decision such as marking an invoice paid, a configured owner OAuth setup can enqueue the invoice PDF for Google Drive archive.',
        current_limitations=(
            'The upload runs through the archive worker and requires GOOGLE_DRIVE_ENABLED=1, owner OAuth credentials, encrypted refresh token storage, and a personal My Drive root folder id.',
            'If Drive is disabled or not configured, the old local stub remains honest and no upload is claimed.',
            'Invoice PDFs are not deleted locally in this MVP; failed uploads keep the local PDF available in Telegram.',
            'This is not SaaS multi-client Drive, not per-client OAuth, and not bank-confirmed settlement.',
            'Service-account mode is unsupported for personal My Drive unless a future Google Workspace/Shared Drive setup is explicitly configured.',
        ),
        runtime_owner='bot/services/invoice_drive_archive_service.py and bot/services/archive_worker.py',
        linked_handlers=('bot/handlers/invoice.py', 'bot/handlers/invoice_followup.py', 'bot/services/google_drive_archive_scheduler.py'),
        truth_source_refs=(
            'docs/Google_Drive_Invoice_Archive_After_Due_Date_Spec.md',
            'docs/Google_Drive_Token_Crypto_Operations.md',
            'docs/Product_Truth_Layer.md',
        ),
        test_refs=('tests/test_google_drive_service_account_archive.py', 'tests/test_invoice_followup_handler.py'),
        safe_next_steps=('Mark a concrete invoice as paid only after confirmation; with Drive configured, the PDF is enqueued and the worker uploads it later.',),
        customization_allowed=True,
        requires_setup=True,
        requires_admin=True,
        requires_external_credentials=True,
        setup_state_keys=('authorized_user', 'supplier_profile', 'google_drive_owner_service_account'),
        forbidden_claims=(
            'The invoice was uploaded to Drive before the worker reports uploaded.',
            'The local invoice PDF was deleted after Drive upload.',
            'This is per-client Google OAuth Drive storage.',
            'Service-account mode works with personal My Drive.',
        ),
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
        capability_id='business_profiles',
        title='Multiple business profiles',
        domain='supplier_profile',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Lets one authorized user list, create, and explicitly switch between isolated business workspaces.',
        current_limitations=(
            'Cross-workspace analytics, one-off per-request overrides, deleting one profile, and multi-member administration are outside MVP.',
            'Existing persisted installations require the approved migration apply gate before public switching can be deployed.',
        ),
        runtime_owner='bot/handlers/business_profiles.py and bot/services/workspace_context.py',
        commands=('/profily',),
        canonical_actions=('switch_business_profile',),
        linked_handlers=(
            'bot/handlers/business_profiles.py',
            'bot/handlers/onboarding.py',
            'bot/services/workspace_context.py',
        ),
        truth_source_refs=(
            'docs/architecture/MULTI_WORKSPACE_BUSINESS_PROFILES_ARCHITECTURE_DESIGN_PROOF.md',
            'docs/llm/Canonical_Action_Registry.md',
            'docs/TZ_FakturaBot.md',
        ),
        test_refs=(
            'tests/test_business_profiles_handler.py',
            'tests/test_workspace_context.py',
            'tests/test_workspace_profile_service.py',
        ),
        safe_next_steps=('Use /profily while idle and select only an accessible profile.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
    ),    _capability(
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
        summary_for_user='Supports confirmation-gated manual/document contact intake and, when enabled for the active workspace, deterministic official Slovak company search by name or IČO with exact-result collapse, bounded suggestions, and official-data prefill.',
        current_limitations=(
            'Registry lookup is disabled by default, may be pilot-workspace limited, requires the external official registry, and reflects the source response rather than guaranteed real-time data.',
            'RPO provides identity/address, not tax identifiers. Optional Financial Administration enrichment uses an audited official mapping but remains separately enabled and credentialed; when disabled, unavailable, invalid, ambiguous, or missing DIČ, the value is typed manually.',
            'IČ DPH is accepted only from validated official data and is never inferred from DIČ; email, IBAN, and contact person are normally manual.',
            'There is no commercial-registry scraping, automatic contact creation from idle attachments, or background synchronization of saved contacts.',
        ),
        runtime_owner='bot/handlers/contacts.py',
        commands=('/contact', '/contact_add', '/add_kontakt'),
        canonical_actions=('add_contact',),
        linked_handlers=('bot/handlers/contacts.py',),
        truth_source_refs=(
            'docs/TZ_FakturaBot.md',
            'docs/Product_Truth_Layer.md',
            'docs/architecture/FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1_ARCHITECTURE_DESIGN_PROOF.md',
            'docs/architecture/FA_CONTACT_REGISTRY_SEARCH_QUALITY_AND_TAX_ENRICHMENT_V1_ARCHITECTURE_DESIGN_PROOF.md',
        ),
        test_refs=(
            'tests/test_contact_intake_semantic_flow.py',
            'tests/test_contact_lookup_normalization.py',
            'tests/test_contact_registry_flow.py',
            'tests/test_contact_registry_services.py',
            'tests/test_contact_iban_migration.py',
            'tests/test_slovak_tax_registry.py',
        ),
        forbidden_claims=(
            'Financial Administration enrichment is active without a verified API mapping, key, and enabled gate.',
            'IČ DPH was inferred or constructed from DIČ.',
            'A suggested company-name match is an exact identity or may be auto-selected.',
            'External official sources are guaranteed real-time or always available.',
        ),
        safe_next_steps=('Use /contact, /contact_add, or /add_kontakt; review official/manual values and explicitly confirm the final save.',),
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
            'Receipt issue dates before 2026 are rejected before confirmed save.',
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
        capability_id='accounting_document_analytics',
        title='Receipt and incoming-invoice analytics',
        domain='accounting_documents',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Runs read-only natural-language analytics over confirmed receipts and incoming invoices for the current workspace.',
        current_limitations=(
            'Partial scope is confirmed expense-side accounting documents only: receipts/bloceky and incoming invoices/prijate faktury in the current workspace.',
            'It can answer bounded read-only questions such as counts, sums, vendor totals, category totals, month filters, comparisons, limited lists, averages, and top rankings.',
            'Categories are confirmed intake metadata only; they are not tax deductibility, VAT reporting, or accounting approval.',
            'It does not analyze outgoing invoices, bank movements, cashflow, VAT/tax reports, accounting export, or full accounting conclusions.',
            'It must not create/edit/delete documents, categories, files, DB rows, registry entries, or other side effects.',
        ),
        runtime_owner='bot/handlers/invoice.py::_run_accounting_document_analytics',
        canonical_actions=('accounting_document_analytics',),
        linked_handlers=(
            'bot/handlers/invoice.py',
            'bot/services/accounting_document_analytics_dataset.py',
            'bot/services/accounting_document_analytics_planner.py',
            'bot/services/accounting_document_analytics_executor.py',
            'bot/services/accounting_document_analytics_answerer.py',
        ),
        truth_source_refs=(
            'docs/llm/Safe_Data_Analyst_Runtime_Checklist.md',
            'docs/llm/Accounting_Document_Analytics_Runtime_Contract.md',
            'docs/llm/Canonical_Action_Registry.md',
            'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md',
            'PROJECT_LOG.md',
        ),
        test_refs=(
            'tests/test_accounting_document_analytics_dataset.py',
            'tests/test_accounting_document_analytics_planner.py',
            'tests/test_accounting_document_analytics_executor.py',
            'tests/test_accounting_document_analytics_answerer.py',
            'tests/test_invoice_intent_prerouter.py',
            'tests/test_voice_state_routing.py',
            'tests/test_product_truth.py',
            'tests/test_info_help.py',
        ),
        safe_next_steps=(
            'Ask a read-only question about confirmed receipts or incoming invoices, for example: Koľko som minul na palivo tento mesiac? or Ukáž sumy podľa kategórií za jún.',
        ),
        customization_allowed=True,
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
        forbidden_claims=(
            'I analyzed outgoing invoices from accounting document analytics.',
            'I changed a receipt, incoming invoice, category, file, or database row from analytics.',
            'I treated receipt categories as tax deductibility or accounting approval.',
            'I analyzed bank movements or cashflow.',
            'I produced a VAT or tax report.',
            'This is full accounting analytics.',
        ),
        notes_for_agents='Partial read-only analytics runtime for confirmed expense-side documents. Python owns workspace-scoped dataset construction, planner bounds, AST validation, sandboxed execution, and Slovak final response grounding.',
    ),
    _capability(
        capability_id='receipt_analytics',
        title='Receipt analytics',
        domain='accounting_documents',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Receipt/blocek analytics is supported partially through the broader accounting_document_analytics read-only runtime over confirmed expense documents.',
        current_limitations=(
            'It covers confirmed receipts/bloceky in the current workspace and may also include incoming invoices when the user asks about expense-side accounting documents.',
            'It supports bounded read-only counts, sums, vendor/category/month grouping, comparisons, and limited lists over confirmed metadata.',
            'Raw OCR, LMM extraction, and confirmed intake categories are not tax deductibility, VAT reporting, or accounting approval.',
            'No bank matching, cashflow analytics, VAT/tax report, accounting export, document mutation, or full accounting analytics is implemented.',
        ),
        runtime_owner='bot/handlers/invoice.py::_run_accounting_document_analytics',
        canonical_actions=('accounting_document_analytics',),
        linked_handlers=(
            'bot/handlers/invoice.py',
            'bot/services/accounting_document_analytics_dataset.py',
            'bot/services/accounting_document_analytics_planner.py',
            'bot/services/accounting_document_analytics_executor.py',
            'bot/services/accounting_document_analytics_answerer.py',
        ),
        truth_source_refs=(
            'docs/llm/Safe_Data_Analyst_Runtime_Checklist.md',
            'docs/llm/Accounting_Document_Analytics_Runtime_Contract.md',
            'docs/Product_Truth_Layer.md',
            'docs/Info_Help_Guidance_Layer.md',
            'docs/TZ_FakturaBot.md',
        ),
        test_refs=(
            'tests/test_accounting_document_analytics_dataset.py',
            'tests/test_accounting_document_analytics_planner.py',
            'tests/test_accounting_document_analytics_executor.py',
            'tests/test_product_truth.py',
            'tests/test_info_help.py',
        ),
        safe_next_steps=(
            'Ask a read-only question about confirmed receipts, for example: Koľko som minul v BAUHAUS? or Koľko bolo bločkov v kategórii materiál?',
        ),
        customization_allowed=True,
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile'),
        forbidden_claims=(
            'Raw OCR is a final accounting category.',
            'I calculated tax deductibility from receipts.',
            'I produced a VAT or tax report from receipts.',
            'I changed receipt metadata from analytics.',
            'This is full accounting analytics.',
        ),
        notes_for_agents='Product Truth alias for receipt-focused questions; runtime is the broader accounting_document_analytics action, not upload/add receipt flow.',
    ),
    _capability(
        capability_id='show_recent_accounting_documents',
        title='Show recent accounting documents',
        domain='accounting_documents',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user='Shows recent confirmed receipt/incoming-invoice metadata in a read-only list.',
        current_limitations=('Not a broad document browser, invoice PDF browser, search, edit, delete, or general Google Drive sync; it may show archive status for confirmed documents.',),
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
        truth_source_refs=('docs/llm/Canonical_Action_Registry.md', 'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md'),
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
        truth_source_refs=('docs/TZ_FakturaBot.md', 'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md'),
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
        truth_source_refs=('docs/Canonical_Decision_Resolver_Contract.md', 'docs/llm/FakturaBot_LLM_Orchestrator_Contract.md'),
        test_refs=('tests/test_invoice_state_decisions.py', 'tests/test_decision_callbacks.py'),
        safe_next_steps=('Use invoice preview controls to edit the draft before approval; nothing is saved until confirmation.',),
        requires_setup=True,
        setup_state_keys=('authorized_user', 'supplier_profile', 'service_alias', 'contact'),
    ),
    _capability(
        capability_id='work_time_tracking',
        title='Work time tracking / Evidencia pracovneho casu',
        domain='work_hours',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Records open/close work days, preview-confirmed manual time ranges or duration-only totals, applies a user lunch-break deduction for reports, generates a monthly Excel work-time report, and can delete one selected month of stored work-time rows after confirmation.',
        current_limitations=(
            'MVP supports one interval per user/day in the current controlled tenant-scoped runtime.',
            'It is not payroll, salary calculation, legal HR attendance compliance, multi-employee dochadzka, accounting/payroll software export, or automatic time detection.',
            'The first report asks once whether lunch break should be deducted; users can later set, change, or disable the fixed lunch-break setting.',
            'Explicit start/end rows report net minutes by subtracting the currently configured lunch break; duration-only rows keep the user-confirmed net duration stable and store a lunch snapshot for audit.',
            'Manual ranges, duration-only totals, ambiguous extracted exact values, lunch-break updates, and monthly deletion require preview confirmation before save/delete.',
            'Deleting a month removes DB work-time records only; generated Excel reports are on-demand files, not canonical stored attendance data.',
        ),
        runtime_owner='bot/handlers/work_time.py and bot/services/work_time.py',
        commands=('/dochadzka',),
        canonical_actions=(
            'open_work_day',
            'close_work_day',
            'add_work_time_entry',
            'generate_work_time_report',
            'update_work_time_lunch_break',
            'delete_work_time_month',
        ),
        linked_handlers=('bot/handlers/work_time.py', 'bot/handlers/invoice.py', 'bot/handlers/voice.py'),
        truth_source_refs=(
            'docs/llm/Canonical_Action_Registry.md',
            'docs/llm/In_Action_Response_Registry.md',
            'docs/TZ_FakturaBot.md',
            'PROJECT_LOG.md',
        ),
        test_refs=('tests/test_work_time_service.py', 'tests/test_work_time_routing.py', 'tests/test_product_truth.py', 'tests/test_info_help.py'),
        safe_next_steps=(
            'Say zacinam pracovny den, zatvor den o 17:00, pracoval som dnes od 5:30 do 17:00, dnes 10 hodin, vytvor vykaz hodin za jun 2026, nastav obednu prestavku na 30 minut, or vymaz dochadzku za jul 2026.',
        ),
        customization_allowed=True,
        requires_setup=True,
        setup_state_keys=('authorized_user',),
        forbidden_claims=(
            'Bot calculates payroll.',
            'Bot calculates salary or wages.',
            'Bot provides legal HR attendance compliance.',
            'Bot provides multi-employee dochadzka.',
            'Bot exports to payroll/accounting software.',
            'Bot provides automatic work-time detection.',
            'Bot automatically knows your work time.',
            'Lunch break settings calculate payroll or legal HR attendance compliance.',
            'Deleting work-time month deletes payroll/legal HR records.',
            'Deleting a month removes generated Excel reports as canonical records.',
            'This Excel is an official payroll document.',
            'This is complete dochadzka for employees.',
        ),
        notes_for_agents='Partial OfficeFlow attendance MVP. Keep payroll/legal/export and multi-employee scope unsupported unless later runtime proves it.',
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
        capability_id='runtime_issue_intake',
        title='Runtime issue intake',
        domain='admin',
        status=ProductTruthStatus.SUPPORTED,
        summary_for_user=(
            'Správca môže uložiť jeden opis pozorovaného problému cez /issue, '
            'ohraničený text alebo hlas bez zrušenia aktuálnej business akcie.'
        ),
        current_limitations=(
            'Iba pre správcu a iba jeden úplný opis v jednej správe; bez príloh, tlačidiel, potvrdenia alebo issue FSM.',
            'Uloženie nepotvrdzuje chybu, nerobí diagnostiku ani opravu a nesľubuje termín.',
            'Automatická údržba, autorepair, merge a deployment nie sú súčasťou tejto funkcie.',
        ),
        runtime_owner='bot/handlers/runtime_issue.py::handle_runtime_issue_capture',
        commands=('/issue',),
        canonical_actions=('report_runtime_issue',),
        linked_handlers=(
            'bot/handlers/runtime_issue.py',
            'bot/handlers/invoice.py',
            'bot/handlers/voice.py',
            'bot/services/active_fsm_guard.py',
            'bot/services/runtime_issue.py',
        ),
        truth_source_refs=(
            'docs/TZ_FakturaBot.md',
            'docs/evals/RUNTIME_ISSUE_INTAKE_V1_conversation_acceptance_proof.md',
            'docs/llm/Canonical_Action_Registry.md',
        ),
        test_refs=(
            'tests/test_runtime_issue_service.py',
            'tests/test_runtime_issue_routes.py',
            'tests/test_runtime_issue_voice.py',
        ),
        safe_next_steps=(
            'Správca pošle /issue a úplný opis v tej istej správe.',
            'Po uložení pokračujte v pôvodnej business akcii; hlásenie ju nezruší.',
        ),
        requires_admin=True,
        forbidden_claims=(
            'Nahlásená chyba je potvrdená.',
            'Problém bude opravený alebo nasadený v konkrétnom termíne.',
            'Hlásenie autorizovalo opravu, merge alebo deployment.',
            'Automatická údržba alebo autorepair sú aktívne.',
        ),
        notes_for_agents=(
            'Stage 1 intake only. Preserve the active business FSM and never '
            'materialize Stage 2 diagnosis, repair, maintenance, or deployment.'
        ),
        supported_channels=('command', 'text', 'voice'),
        unsupported_channels=('button', 'file', 'attachment'),
        last_verified_at='2026-07-28',
    ),
    _capability(
        capability_id='info_help',
        title='InfoHelp guidance',
        domain='info_help',
        status=ProductTruthStatus.PARTIAL,
        summary_for_user='Current runtime keeps the bounded Unknown / Discovery / Triage v1 and post-rollback InfoHelp by default, and includes a rollout-gated contextual V2 assistant that extracts exact business object/operation, speech act, correction, negation, command typo, explicit reply, recent process-memory context, and active-flow questions before Python validation.',
        current_limitations=(
            'This remains a partial Level 2 foundation built on bounded triage v1; Contextual V2 is disabled by default and admin_pilot/enabled modes require explicit runtime configuration.',
            'Full Level 2 still requires broader bounded InfoHelp resolver coverage, voice/STT parity across the full surface, multilingual and noisy-input evaluation, and account-context-aware runtime evidence.',
            'InfoHelp can describe selected human-review capabilities, but does not itself save requests, send admin responses, mutate Product Truth, or hand off code-agent work.',
            'The assistant call is interpretation only. Python revalidates Product Truth, exact domain/object/operation, action owner, slots, FSM, tenant scope, confirmation and side effects.',
            'Recent context is process-memory only, limited to three user and three bot turns for ten minutes, isolated by user/chat/workspace, and lost on restart.',
            'Interactive Telegram admin-pilot acceptance is still pending; this is not unrestricted arbitrary-request understanding or permanent learning.',
        ),
        runtime_owner='bot/services/info_help.py::build_product_truth_guidance, build_info_help_triage_guidance, and build_top_level_unknown_guidance; bot/services/info_help_resolver.py; bot/services/info_help_action_registry.py; bot/services/info_help_context.py; bot/handlers/invoice.py; bot/services/active_fsm_guard.py',
        linked_handlers=('bot/services/info_help.py', 'bot/handlers/invoice.py', 'bot/services/active_fsm_guard.py'),
        truth_source_refs=('docs/Info_Help_Guidance_Layer.md', 'PROJECT_LOG.md'),
        test_refs=('tests/test_product_truth.py', 'tests/test_info_help.py', 'tests/test_info_help_contextual_v2.py', 'tests/test_info_help_contextual_journeys_v2.py', 'tests/test_invoice_reference_continuation_v2.py'),
        safe_next_steps=(
            'Keep INFOHELP_CONTEXTUAL_V2_ROLLOUT=disabled until reviewed admin-pilot Telegram journeys pass.',
            'Use exact Product Truth/action semantics and existing continuation/confirmation owners; never substitute a nearby object action.',
        ),
        forbidden_claims=(
            'InfoHelp Level 2 is complete.',
            'I can answer any product capability question.',
            'InfoHelp saved your customization request.',
            'InfoHelp sent an admin response.',
            'InfoHelp permanently learned this conversation.',
            'A side effect occurred because InfoHelp understood the intent.',
        ),
        supported_channels=('text', 'command', 'voice'),
        unsupported_channels=('attachment',),
        notes_for_agents='Contextual V2 is implemented behind a fail-closed disabled/admin_pilot/enabled gate and remains partial pending live Telegram acceptance.',
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
