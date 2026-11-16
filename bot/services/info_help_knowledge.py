"""Product evidence and bounded workspace reads for conversational InfoHelp."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from bot.config import Config
from bot.services.accounting_document_archive_service import (
    read_receipt_archive_coverage,
    read_receipt_archive_status,
)
from bot.services.accounting_document_models import DOCUMENT_TYPE_RECEIPT
from bot.services.accounting_document_registry import list_recent_accounting_documents
from bot.services.info_help import build_contextual_read_answer
from bot.services.product_truth import get_capability, list_capabilities
from bot.services.scoped_invoice_runtime import ScopedInvoiceRuntime
from bot.services.work_time import WorkTimeService
from bot.services.workspace_context import WorkspaceContext


_DRIVE_SHARING = 'google_drive_folder_sharing'
_RELEASE_NOTES = 'recent_product_updates'
_ACTION_EXAMPLES = {
    'show_existing_invoice': ('zobraz faktúru 02',),
    'edit_existing_invoice': ('uprav faktúru 02',),
    'work_time_tracking': (
        'zatvor den o 17:00',
        'oprav odchod 9.9.2026 na 13:10',
    ),
}
_CAPABILITIES = {cap.capability_id: cap.title for cap in list_capabilities()}
KNOWLEDGE_INDEX = {
    **_CAPABILITIES,
    'add_receipt_or_incoming_invoice': (
        'Receipt and incoming invoice intake: accepted input, issue or purchase date rules, '
        'confirmation, validation, saving and supported management of confirmed documents'
    ),
    'show_existing_invoice': 'Find and display a saved outgoing invoice by number, suffix or latest',
    'edit_existing_invoice': 'Edit fields on a saved outgoing invoice; text and voice restrictions',
    'work_time_tracking': 'Attendance, recorded hours, lunch calculation, corrections and monthly Excel',
    'google_drive_invoice_storage': 'Google Drive archive configuration and delivery after local save',
    _DRIVE_SHARING: 'Give an accountant read access to the archive folder for one profile',
    _RELEASE_NOTES: 'Recent user-facing OfficeFlow changes and release notes',
}

WORKSPACE_FACTS = {
    'active_profile': 'Name of the currently selected business profile',
    'receipt_archive': 'Actual Drive configuration and recorded upload coverage of already confirmed receipts',
    'invoice_period': 'Count and amounts of outgoing invoices by invoice issue date',
    'latest_invoice': 'Number, issue date, amount and currency of the latest outgoing invoice',
    'receipt_period': 'Actual count and totals by currency of all confirmed receipts in a date period',
    'work_time_month': 'Net minutes and row count in the selected month',
    'day_break_availability': 'Whether the per-day lunch break editor is enabled and its schema is ready',
}


def read_knowledge(ids: list[str]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for article_id in ids:
        if article_id == _DRIVE_SHARING:
            evidence[article_id] = {
                'guidance': build_contextual_read_answer(
                    topic='drive_folder_sharing', language='en', profile=None,
                    archive_status='unknown', upload_date=None,
                ),
                'sharing_boundary': (
                    'Giving access to the entire profile folder can also expose incoming invoices '
                    'and other contents. Share only the receipt folder for receipt-only access.'
                ),
                'source': 'docs/Info_Help_Guidance_Layer.md',
            }
        elif article_id == _RELEASE_NOTES:
            evidence[article_id] = {
                'published_release_notes': build_contextual_read_answer(
                    topic='product_updates', language='en', profile=None,
                    archive_status='unknown', upload_date=None,
                ),
                'source': 'CHANGELOG.md#user-facing-release-notes',
            }
        elif article_id in _CAPABILITIES:
            capability = get_capability(article_id).capability
            examples = _ACTION_EXAMPLES.get(article_id, ())
            evidence[article_id] = {
                'status': capability.status.value,
                'summary': capability.summary_for_user,
                'limits': capability.current_limitations,
                'next_steps': examples or capability.safe_next_steps,
                'commands': capability.commands,
                'action_examples_for_this_chat': examples,
                'forbidden_claims': capability.forbidden_claims,
                'sources': capability.truth_source_refs,
            }
    return evidence


def read_workspace_fact(
    *, config: Config, workspace: WorkspaceContext | None, actor_id: int,
    fact: str, year: int | None, month: int | None,
) -> dict[str, Any]:
    if workspace is None:
        return {'status': 'profile_unavailable', 'next_step': '/profily'}
    if fact == 'active_profile':
        return {'profile': workspace.workspace_display_name}
    if fact == 'receipt_archive':
        status, last_upload_date = read_receipt_archive_status(config, workspace)
        coverage = read_receipt_archive_coverage(config, workspace)
        return {
            'profile': workspace.workspace_display_name,
            'configuration_status': status,
            'last_successful_upload_date': last_upload_date,
            'coverage': asdict(coverage) if coverage is not None else None,
            'receipts_without_upload_confirmation': (
                coverage.total - coverage.uploaded if coverage is not None else None
            ),
            'coverage_scope': 'local records for confirmed receipts in this profile',
            'coverage_meaning': (
                'All receipts counted here are confirmed and already saved locally. Uploaded '
                'requires a recorded Drive file ID. Pending means there is a recorded pending '
                'or retrying job. Unknown refers only to the Drive upload status, never to the '
                'local save, and must never be described as uploaded, pending, or failed.'
            ),
        }
    if fact == 'day_break_availability':
        service = WorkTimeService(config.db_path, workspace_id=workspace.workspace_id)
        return {'available': config.work_time_day_break_enabled and service.day_break_schema_ready()}
    if fact == 'latest_invoice':
        latest = _invoice_runtime(config, workspace, actor_id).get_latest_invoice()
        return {
            'invoice_number': latest.invoice_number,
            'issue_date': latest.issue_date,
            'amount': latest.total_amount,
            'currency': latest.currency,
        } if latest is not None else {'status': 'no_invoices'}
    if year is None or not 1900 <= year <= 2100 or (month is not None and not 1 <= month <= 12):
        return {'status': 'invalid_period'}
    if fact == 'work_time_month':
        if month is None:
            return {'status': 'month_required'}
        return asdict(WorkTimeService(config.db_path, workspace_id=workspace.workspace_id).summarize_month(
            telegram_id=actor_id, year=year, month=month,
        ))
    start = date(year, month or 1, 1).isoformat()
    end = date(year, month or 12, monthrange(year, month or 12)[1]).isoformat()
    if fact == 'invoice_period':
        summary = _invoice_runtime(config, workspace, actor_id).summarize_period(start_date=start, end_date=end)
        return {
            'start_date': start,
            'end_date': end,
            'count': summary.invoice_count,
            'totals_by_currency': [asdict(item) for item in summary.totals_by_currency],
        }
    if fact == 'receipt_period':
        return _receipt_period(config, workspace, start, end)
    return {'status': 'unknown_fact'}


def _invoice_runtime(config: Config, workspace: WorkspaceContext, actor_id: int) -> ScopedInvoiceRuntime:
    return ScopedInvoiceRuntime(
        db_path=config.db_path, storage_dir=config.storage_dir,
        actor_telegram_id=actor_id, context=workspace,
    )


def _receipt_period(config: Config, workspace: WorkspaceContext, start: str, end: str) -> dict[str, Any]:
    documents = list_recent_accounting_documents(
        storage_dir=config.storage_dir, workspace_key=workspace.storage_key, limit=None,
    )
    totals: dict[str, Decimal] = defaultdict(Decimal)
    count = incomplete_amounts = 0
    for document in documents:
        if document.document_type != DOCUMENT_TYPE_RECEIPT or not document.issue_date:
            continue
        if not start <= document.issue_date <= end:
            continue
        count += 1
        try:
            amount = Decimal(document.total_amount or '')
        except InvalidOperation:
            incomplete_amounts += 1
            continue
        if not amount.is_finite() or not document.currency:
            incomplete_amounts += 1
            continue
        totals[document.currency] += amount
    return {
        'start_date': start,
        'end_date': end,
        'count': count,
        'totals_by_currency': {currency: str(amount) for currency, amount in sorted(totals.items())},
        'incomplete_amounts': incomplete_amounts,
    }
