from datetime import date

import pandas as pd
import pytest

from bot.services.accounting_document_analytics_executor import (
    AccountingDocumentAnalyticsCodeValidationError,
    execute_accounting_document_analytics_code,
)


def _dataframe() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                'document_type': 'receipt',
                'issue_date': '2026-06-01',
                'vendor_name': 'BAUHAUS',
                'total_amount': 13.83,
                'currency': 'EUR',
                'category_label': 'Material',
            },
            {
                'document_type': 'incoming_invoice',
                'issue_date': '2026-06-12',
                'vendor_name': 'BAUHAUS',
                'total_amount': 100.0,
                'currency': 'EUR',
                'category_label': 'Material',
            },
            {
                'document_type': 'receipt',
                'issue_date': '2026-05-03',
                'vendor_name': 'Shell',
                'total_amount': 50.0,
                'currency': 'EUR',
                'category_label': 'Fuel',
            },
        ]
    )


def test_accounting_document_analytics_executor_runs_read_only_pandas_code() -> None:
    execution = execute_accounting_document_analytics_code(
        code=(
            'df = accounting_documents_df.copy()\n'
            "df['issue_date'] = pd.to_datetime(df['issue_date'], errors='coerce')\n"
            "mask = (df['issue_date'].dt.year == current_date.year) & (df['issue_date'].dt.month == 6)\n"
            'subset = df[mask]\n'
            "grouped = subset.groupby(['vendor_name', 'currency'], as_index=False)['total_amount'].sum()\n"
            "result = {'summary': {'count': int(len(subset)), 'total': float(subset['total_amount'].sum())}, 'tables': {'by_vendor': grouped.to_dict(orient='records')}, 'warnings': [], 'answer_hints': []}"
        ),
        accounting_documents_df=_dataframe(),
        current_date=date(2026, 6, 21),
    )

    assert execution.result['summary']['count'] == 2
    assert execution.result['summary']['total'] == 113.83
    assert execution.result['tables']['by_vendor'][0]['vendor_name'] == 'BAUHAUS'


@pytest.mark.parametrize(
    'code',
    [
        'import os\nresult = {}',
        "df = pd.read_csv('x.csv')\nresult = {}",
        "open('x.txt', 'w')\nresult = {}",
        "df = accounting_documents_df.copy()\nfor row in []:\n    pass\nresult = {}",
        "df = [x for x in []]\nresult = {}",
    ],
)
def test_accounting_document_analytics_executor_rejects_unsafe_code(code: str) -> None:
    with pytest.raises(AccountingDocumentAnalyticsCodeValidationError):
        execute_accounting_document_analytics_code(
            code=code,
            accounting_documents_df=_dataframe(),
            current_date=date(2026, 6, 21),
        )
