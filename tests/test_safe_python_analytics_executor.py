from datetime import date
import multiprocessing as mp

import pytest

pd = pytest.importorskip('pandas')

from bot.services.safe_python_analytics_executor import (
    AnalyticsCodeValidationError,
    AnalyticsExecutionError,
    execute_invoice_analytics_code,
)


def _df():
    return pd.DataFrame(
        [
            {
                'invoice_id': 1,
                'invoice_number': '20250001',
                'issue_date': '2025-05-10',
                'delivery_date': '2025-05-10',
                'due_date': '2025-05-24',
                'total_amount': 100.0,
                'currency': 'EUR',
                'invoice_status_raw': 'created',
                'payment_status_canonical': 'paid',
                'payment_status_label': 'uhradena',
                'payment_status_source': 'invoice_followup_state',
                'customer_name': 'Alpha',
                'contact_id': 1,
                'has_pdf': True,
            },
            {
                'invoice_id': 2,
                'invoice_number': '20260001',
                'issue_date': '2026-05-11',
                'delivery_date': '2026-05-11',
                'due_date': '2026-05-25',
                'total_amount': 300.0,
                'currency': 'EUR',
                'invoice_status_raw': 'created',
                'payment_status_canonical': 'overdue',
                'payment_status_label': 'po splatnosti',
                'payment_status_source': 'derived_missing_followup_state',
                'customer_name': 'Beta',
                'contact_id': 2,
                'has_pdf': False,
            },
            {
                'invoice_id': 3,
                'invoice_number': '20260002',
                'issue_date': '2026-06-01',
                'delivery_date': '2026-06-01',
                'due_date': '2026-06-30',
                'total_amount': 200.0,
                'currency': 'USD',
                'invoice_status_raw': 'paid',
                'payment_status_canonical': 'pending_payment',
                'payment_status_label': 'caka na uhradu',
                'payment_status_source': 'derived_missing_followup_state',
                'customer_name': 'Beta',
                'contact_id': 2,
                'has_pdf': True,
            },
        ]
    )


def _execute(code: str):
    return execute_invoice_analytics_code(
        code=code,
        invoices_df=_df(),
        current_date=date(2026, 6, 16),
    ).result


def test_simple_count_works() -> None:
    result = _execute(
        'df = invoices_df.copy()\n'
        'result = {"summary": {"invoice_count": int(len(df))}, "tables": {}, "warnings": [], "answer_hints": []}'
    )
    assert result['summary']['invoice_count'] == 3


def test_sum_by_currency_works() -> None:
    result = _execute(
        'df = invoices_df.copy()\n'
        'grouped = df.groupby("currency")["total_amount"].sum().round(2).to_dict()\n'
        'result = {"summary": {"totals_by_currency": grouped}, "tables": {}, "warnings": [], "answer_hints": []}'
    )
    assert result['summary']['totals_by_currency'] == {'EUR': 400.0, 'USD': 200.0}


def test_compare_may_2026_vs_may_2025_works() -> None:
    result = _execute(
        'df = invoices_df.copy()\n'
        'df["issue_dt"] = pd.to_datetime(df["issue_date"], errors="coerce")\n'
        'may_2026 = df[(df["issue_dt"].dt.year == 2026) & (df["issue_dt"].dt.month == 5)]["total_amount"].sum()\n'
        'may_2025 = df[(df["issue_dt"].dt.year == 2025) & (df["issue_dt"].dt.month == 5)]["total_amount"].sum()\n'
        'result = {"summary": {"may_2026": float(may_2026), "may_2025": float(may_2025), "difference": float(may_2026 - may_2025)}, "tables": {}, "warnings": [], "answer_hints": []}'
    )
    assert result['summary'] == {'may_2026': 300.0, 'may_2025': 100.0, 'difference': 200.0}


def test_list_invoices_for_may_works() -> None:
    result = _execute(
        'df = invoices_df.copy()\n'
        'df["issue_dt"] = pd.to_datetime(df["issue_date"], errors="coerce")\n'
        'may = df[df["issue_dt"].dt.month == 5]\n'
        'rows = may[["invoice_number", "customer_name", "total_amount"]].to_dict(orient="records")\n'
        'result = {"summary": {"count": int(len(may))}, "tables": {"may_invoices": rows}, "warnings": [], "answer_hints": []}'
    )
    assert result['summary']['count'] == 2
    assert result['tables']['may_invoices'][0]['invoice_number'] == '20250001'


def test_payment_status_count_uses_normalized_canonical_column() -> None:
    result = _execute(
        'df = invoices_df.copy()\n'
        'counts = df.groupby("payment_status_canonical")["invoice_id"].count().to_dict()\n'
        'result = {"summary": {"payment_status_counts": counts}, "tables": {}, "warnings": [], "answer_hints": []}'
    )
    assert result['summary']['payment_status_counts'] == {'overdue': 1, 'paid': 1, 'pending_payment': 1}


def test_unpaid_filter_includes_pending_payment_and_overdue() -> None:
    result = _execute(
        'df = invoices_df.copy()\n'
        'unpaid = df[df["payment_status_canonical"].isin(["pending_payment", "overdue"])]\n'
        'rows = unpaid[["invoice_number", "payment_status_canonical"]].to_dict(orient="records")\n'
        'result = {"summary": {"count": int(len(unpaid))}, "tables": {"unpaid_invoices": rows}, "warnings": [], "answer_hints": []}'
    )

    assert result['summary']['count'] == 2
    assert [row['invoice_number'] for row in result['tables']['unpaid_invoices']] == ['20260001', '20260002']


@pytest.mark.parametrize(
    'code',
    [
        'import os\nresult = {}',
        'df = invoices_df.copy()\nf = open("x")\nresult = {}',
        'df = invoices_df.copy()\nvalue = eval("1+1")\nresult = {}',
        'df = invoices_df.copy()\nos.system("echo x")\nresult = {}',
        'df = invoices_df.copy()\nklass = df.__class__\nresult = {}',
        'df = invoices_df.copy()\nrows = pd.read_csv("x.csv")\nresult = {}',
        'df = invoices_df.copy()\nrows = pd.read_sql("SELECT * FROM invoice", None)\nresult = {}',
        'df = invoices_df.copy()\ndf.to_csv("x.csv")\nresult = {}',
        'df = invoices_df.copy()\nwhile True:\n    pass\nresult = {}',
        'df = invoices_df.copy()\nfor value in range(3):\n    df = df\nresult = {}',
        'df = invoices_df.copy()\nrows = [str(i) for i in range(3)]\nresult = {}',
        'df = invoices_df.copy()\nwith pd.option_context("mode.chained_assignment", None):\n    result = {}',
    ],
)
def test_forbidden_code_is_rejected(code: str) -> None:
    with pytest.raises(AnalyticsCodeValidationError):
        execute_invoice_analytics_code(code=code, invoices_df=_df(), current_date=date(2026, 6, 16))


def test_code_without_result_is_rejected() -> None:
    with pytest.raises(AnalyticsCodeValidationError):
        execute_invoice_analytics_code(code='df = invoices_df.copy()', invoices_df=_df(), current_date=date(2026, 6, 16))


def test_runtime_exception_returns_safe_failure() -> None:
    with pytest.raises(AnalyticsExecutionError):
        execute_invoice_analytics_code(
            code='df = invoices_df.copy()\nvalue = 1 / 0\nresult = {}',
            invoices_df=_df(),
            current_date=date(2026, 6, 16),
        )


def test_process_timeout_returns_safe_failure_and_leaves_no_active_child() -> None:
    before_pids = {child.pid for child in mp.active_children()}
    with pytest.raises(AnalyticsExecutionError) as exc_info:
        execute_invoice_analytics_code(
            code=(
                'df = invoices_df.copy()\n'
                'result = {"summary": {"invoice_count": int(len(df))}, "tables": {}, "warnings": [], "answer_hints": []}'
            ),
            invoices_df=_df(),
            current_date=date(2026, 6, 16),
            timeout_seconds=0.0001,
        )

    assert str(exc_info.value) == 'execution_timeout'
    after_pids = {child.pid for child in mp.active_children()}
    assert after_pids <= before_pids


def test_huge_output_is_limited() -> None:
    result = _execute(
        'df = invoices_df.copy()\n'
        'rows_df = pd.DataFrame({"value": ["x" * 200] * 200})\n'
        'rows = rows_df.to_dict(orient="records")\n'
        'result = {"summary": {"count": int(len(rows_df))}, "tables": {"rows": rows}, "warnings": [], "answer_hints": []}'
    )
    assert len(result['tables']['rows']) <= 20 or result['tables'] == {}
    assert result['warnings']
