from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd

from bot.services.db import managed_connection
from bot.services.invoice_analytics_dataset import (
    INVOICE_ANALYTICS_COLUMNS,
    _normalize_payment_status,
)
from bot.services.workspace_context import WorkspaceContext


class WorkspaceInvoiceAnalyticsSchemaRequired(RuntimeError):
    pass


class WorkspaceInvoiceAnalyticsDatasetService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def build_invoice_dataframe(
        self,
        context: WorkspaceContext,
        *,
        current_date: date,
    ) -> pd.DataFrame:
        if not self._db_path.exists():
            return pd.DataFrame(columns=INVOICE_ANALYTICS_COLUMNS)

        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT i.id AS invoice_id, i.invoice_number, i.issue_date, '
                    'i.delivery_date, i.due_date, i.total_amount, i.currency, '
                    'i.status AS invoice_status_raw, '
                    's.invoice_id AS followup_state_invoice_id, '
                    's.payment_status AS followup_payment_status, '
                    "COALESCE(c.name, '') AS customer_name, i.contact_id, "
                    'CASE WHEN i.pdf_path IS NOT NULL AND TRIM(i.pdf_path) != \'\' '
                    'THEN 1 ELSE 0 END AS has_pdf '
                    'FROM invoice i '
                    'LEFT JOIN contact c '
                    'ON c.id = i.contact_id AND c.workspace_id = i.workspace_id '
                    'LEFT JOIN invoice_followup_state s '
                    'ON s.invoice_id = i.id AND s.workspace_id = i.workspace_id '
                    'WHERE i.workspace_id = ? '
                    'ORDER BY i.issue_date ASC, i.invoice_number ASC, i.id ASC'
                ),
                (context.workspace_id,),
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
                    'customer_name': str(row['customer_name'] or '').strip()
                    or 'Neznamy odberatel',
                    'contact_id': int(row['contact_id'])
                    if row['contact_id'] is not None
                    else None,
                    'has_pdf': bool(row['has_pdf']),
                }
            )

        dataframe = pd.DataFrame.from_records(records, columns=INVOICE_ANALYTICS_COLUMNS)
        if not dataframe.empty:
            dataframe['total_amount'] = pd.to_numeric(
                dataframe['total_amount'], errors='coerce'
            ).fillna(0.0)
            dataframe['has_pdf'] = dataframe['has_pdf'].astype(bool)
        return dataframe

    @staticmethod
    def _require_schema(connection: sqlite3.Connection) -> None:
        for table in ('invoice', 'contact', 'invoice_followup_state'):
            columns = {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}
            if 'workspace_id' not in columns:
                raise WorkspaceInvoiceAnalyticsSchemaRequired(
                    f'workspace_{table}_schema_migration_required'
                )
