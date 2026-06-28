from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import sqlite3
from typing import Any
import unicodedata

import pandas as pd

from bot.services.db import managed_connection


INVOICE_ANALYTICS_COLUMNS = (
    'invoice_id',
    'invoice_number',
    'issue_date',
    'delivery_date',
    'due_date',
    'total_amount',
    'currency',
    'invoice_status_raw',
    'payment_status_canonical',
    'payment_status_label',
    'payment_status_source',
    'customer_name',
    'contact_id',
    'has_pdf',
)

_PAYMENT_STATUS_LABELS = {
    'pending_payment': 'caka na uhradu',
    'paid': 'uhradena',
    'overdue': 'po splatnosti',
    'unknown': 'neznamy stav',
}

PAYMENT_STATUS_FILTER_GROUPS = {
    'unpaid': ('pending_payment', 'overdue'),
    'pending_payment': ('pending_payment',),
    'overdue': ('overdue',),
    'paid': ('paid',),
    'unknown': ('unknown',),
}

_PAYMENT_STATUS_FILTER_ALIASES = {
    'overdue': (
        'overdue',
        'po splatnosti',
        'po termine splatnosti',
        'omeskanie',
        'omeskanim',
        'meska',
        '\u043f\u0440\u043e\u0441\u0442\u0440\u043e\u0447\u0435\u043d\u0456',
        '\u043f\u0440\u043e\u0441\u0442\u0440\u043e\u0447\u0435\u043d\u0456\u0457',
        '\u043f\u0440\u043e\u0441\u0440\u043e\u0447\u0435\u043d\u043d\u044b\u0435',
    ),
    'pending_payment': (
        'pending payment',
        'caka na uhradu',
        'cakaju na uhradu',
        'pred splatnostou',
        'este v splatnosti',
    ),
    'unpaid': (
        'unpaid',
        'not paid',
        'not-paid',
        'unsettled',
        'nezaplatene',
        'nezaplatena',
        'nezaplatenych',
        'neuhradene',
        'neuhradena',
        'neuhradenych',
        'neplatene',
        '\u043d\u0435\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u0456',
        '\u043d\u0435\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u0456\u0457',
        '\u043d\u0435\u0441\u043f\u043b\u0430\u0447\u0435\u043d\u0456',
        '\u043d\u0435\u0437\u0430\u043f\u043b\u0430\u0447\u0435\u043d\u0456',
        '\u043d\u0435\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u043d\u044b\u0435',
        '\u043d\u0435\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u043d\u044b\u0445',
    ),
    'paid': (
        'paid',
        'uhradene',
        'uhradena',
        'uhradenych',
        'zaplatene',
        'zaplatenych',
        '\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u0456',
        '\u0441\u043f\u043b\u0430\u0447\u0435\u043d\u0456',
        '\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u043d\u044b\u0435',
    ),
    'unknown': (
        'unknown status',
        'neznamy stav',
        'nejasny stav',
    ),
}


@dataclass(frozen=True)
class InvoiceAnalyticsDatasetMetadata:
    supplier_telegram_id: int
    row_count: int
    columns: tuple[str, ...]


class InvoiceAnalyticsDatasetService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def build_invoice_dataframe_for_supplier(
        self,
        *,
        supplier_telegram_id: int,
        current_date: date,
    ) -> pd.DataFrame:
        if not self._db_path.exists():
            return pd.DataFrame(columns=INVOICE_ANALYTICS_COLUMNS)

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT '
                    'i.id AS invoice_id, '
                    'i.invoice_number AS invoice_number, '
                    'i.issue_date AS issue_date, '
                    'i.delivery_date AS delivery_date, '
                    'i.due_date AS due_date, '
                    'i.total_amount AS total_amount, '
                    'i.currency AS currency, '
                    'i.status AS invoice_status_raw, '
                    's.invoice_id AS followup_state_invoice_id, '
                    's.payment_status AS followup_payment_status, '
                    'COALESCE(c.name, \'\') AS customer_name, '
                    'i.contact_id AS contact_id, '
                    'CASE WHEN i.pdf_path IS NOT NULL AND TRIM(i.pdf_path) != \'\' THEN 1 ELSE 0 END AS has_pdf '
                    'FROM invoice i '
                    'LEFT JOIN contact c '
                    'ON c.id = i.contact_id AND c.supplier_telegram_id = i.supplier_telegram_id '
                    'LEFT JOIN invoice_followup_state s '
                    'ON s.invoice_id = i.id AND s.supplier_telegram_id = i.supplier_telegram_id '
                    'WHERE i.supplier_telegram_id = ? '
                    'ORDER BY i.issue_date ASC, i.invoice_number ASC, i.id ASC'
                ),
                (supplier_telegram_id,),
            ).fetchall()

        records: list[dict[str, Any]] = []
        for row in rows:
            payment_status = _normalize_payment_status(
                followup_payment_status=row['followup_payment_status'],
                has_followup_state=row['followup_state_invoice_id'] is not None,
                due_date_value=row['due_date'],
                current_date=current_date,
            )
            records.append(
                {
                    'invoice_id': int(row['invoice_id']),
                    'invoice_number': str(row['invoice_number'] or ''),
                    'issue_date': str(row['issue_date'] or ''),
                    'delivery_date': str(row['delivery_date'] or ''),
                    'due_date': str(row['due_date'] or ''),
                    'total_amount': float(row['total_amount'] or 0.0),
                    'currency': str(row['currency'] or '').strip().upper() or 'UNKNOWN',
                    'invoice_status_raw': str(row['invoice_status_raw'] or '').strip(),
                    'payment_status_canonical': payment_status['canonical'],
                    'payment_status_label': payment_status['label'],
                    'payment_status_source': payment_status['source'],
                    'customer_name': str(row['customer_name'] or '').strip() or 'Neznamy odberatel',
                    'contact_id': int(row['contact_id']) if row['contact_id'] is not None else None,
                    'has_pdf': bool(row['has_pdf']),
                }
            )

        dataframe = pd.DataFrame.from_records(records, columns=INVOICE_ANALYTICS_COLUMNS)
        if not dataframe.empty:
            dataframe['total_amount'] = pd.to_numeric(dataframe['total_amount'], errors='coerce').fillna(0.0)
            dataframe['has_pdf'] = dataframe['has_pdf'].astype(bool)
        return dataframe


def _normalize_payment_status(
    *,
    followup_payment_status: Any,
    has_followup_state: bool,
    due_date_value: Any,
    current_date: date,
) -> dict[str, str]:
    raw_status = str(followup_payment_status or '').strip().lower()
    if raw_status == 'paid':
        canonical = 'paid'
        source = 'invoice_followup_state'
    elif has_followup_state and not raw_status:
        canonical = 'unknown'
        source = 'missing_payment_status'
    elif raw_status and raw_status != 'unpaid':
        canonical = 'unknown'
        source = 'invoice_followup_state_unknown'
    else:
        due_date = _parse_iso_date(due_date_value)
        if due_date is None:
            canonical = 'unknown'
            source = 'missing_due_date'
        elif due_date < current_date:
            canonical = 'overdue'
            source = 'invoice_followup_state' if raw_status == 'unpaid' else 'derived_missing_followup_state'
        else:
            canonical = 'pending_payment'
            source = 'invoice_followup_state' if raw_status == 'unpaid' else 'derived_missing_followup_state'
    return {
        'canonical': canonical,
        'label': _PAYMENT_STATUS_LABELS[canonical],
        'source': source,
    }


def _parse_iso_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or '').strip())
    except ValueError:
        return None


def _analytics_alias_key(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', str(value).casefold().strip())
    without_diacritics = ''.join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r'\s+', ' ', re.sub(r'[^\w]+', ' ', without_diacritics, flags=re.UNICODE)).strip('_ ')


def resolve_payment_status_filter_hints(user_question: str) -> list[dict[str, Any]]:
    normalized_question = _analytics_alias_key(user_question)
    if not normalized_question:
        return []
    padded_question = f' {normalized_question} '
    for filter_group in ('overdue', 'pending_payment', 'unpaid', 'paid', 'unknown'):
        for alias in _PAYMENT_STATUS_FILTER_ALIASES[filter_group]:
            normalized_alias = _analytics_alias_key(alias)
            if normalized_alias and f' {normalized_alias} ' in padded_question:
                return [
                    {
                        'filter_group': filter_group,
                        'canonical_values': list(PAYMENT_STATUS_FILTER_GROUPS[filter_group]),
                        'matched_alias': normalized_alias,
                    }
                ]
    return []


def build_invoice_analytics_data_catalog(*, user_question: str = '') -> dict[str, Any]:
    return {
        'datasets': {
            'invoices_df': {
                'description': 'Outgoing invoices for the current supplier only.',
                'columns': {
                    'invoice_id': 'Integer internal invoice id, scoped to current supplier dataset.',
                    'invoice_number': 'Invoice number as a string.',
                    'issue_date': 'Invoice issue date as ISO date string YYYY-MM-DD.',
                    'delivery_date': 'Delivery date as ISO date string YYYY-MM-DD.',
                    'due_date': 'Due date as ISO date string YYYY-MM-DD.',
                    'total_amount': 'Invoice total amount as numeric value.',
                    'currency': 'Currency code, normalized uppercase where possible.',
                    'invoice_status_raw': 'Raw invoice lifecycle status stored on the invoice row; do not use it as payment truth.',
                    'payment_status_canonical': (
                        'Bot stored/derived payment state: pending_payment, paid, overdue, or unknown. '
                        'This is based on invoice_followup_state.payment_status plus due_date/current_date. '
                        'It is not bank-confirmed settlement unless bank reconciliation is implemented later.'
                    ),
                    'payment_status_label': 'Human-readable label for payment_status_canonical.',
                    'payment_status_source': 'Where the payment status came from: invoice_followup_state, derived_missing_followup_state, missing_payment_status, missing_due_date, or invoice_followup_state_unknown.',
                    'customer_name': 'Customer/contact display name, joined by Python.',
                    'contact_id': 'Current supplier contact id, or null when missing.',
                    'has_pdf': 'Boolean flag that says whether a PDF path exists; absolute paths are not exposed.',
                },
                'payment_status_examples': {
                    'pending_payment': 'not marked paid and due date is today or in the future',
                    'paid': 'marked paid in the bot follow-up/payment state',
                    'overdue': 'not marked paid and due date is before current_date',
                    'unknown': 'required payment or due-date fields are missing or inconsistent',
                },
            }
        },
        'payment_status_filter_groups': [
            {
                'filter_group': key,
                'canonical_values': list(values),
            }
            for key, values in PAYMENT_STATUS_FILTER_GROUPS.items()
        ],
        'payment_status_filter_hints': resolve_payment_status_filter_hints(user_question),
        'payment_status_filter_contract': (
            'For unpaid/not paid/neuhradene/nezaplatene/neoplatene questions, filter '
            'payment_status_canonical by both pending_payment and overdue. Do not implement unpaid as '
            'pending_payment only. For overdue/po splatnosti questions, filter overdue only. '
            'For paid/uhradene questions, filter paid only. Reminder mute/snooze state is not payment truth.'
        ),
        'forbidden': [
            'No receipts or incoming invoices.',
            'No bank movements.',
            'No tax/legal/accounting advice.',
            'No DB writes, file access, SQL, or cross-tenant data.',
        ],
    }
