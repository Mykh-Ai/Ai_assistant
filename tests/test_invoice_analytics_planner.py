import pytest

from bot.services.invoice_analytics_planner import (
    InvoiceAnalyticsPlanError,
    parse_invoice_analytics_plan,
)
from bot.services.safe_python_analytics_executor import (
    AnalyticsCodeValidationError,
    validate_analytics_code,
)


def test_valid_invoice_analytics_plan_is_accepted() -> None:
    plan = parse_invoice_analytics_plan(
        '{"analysis_code":"df = invoices_df.copy()\\nresult = {\\"summary\\": {\\"count\\": int(len(df))}, \\"tables\\": {}, \\"warnings\\": [], \\"answer_hints\\": []}","answer_language":"uk","reasoning_summary":"count invoices"}'
    )

    assert 'invoices_df.copy()' in plan.analysis_code
    assert plan.answer_language == 'uk'
    assert plan.reasoning_summary == 'count invoices'


def test_invoice_analytics_plan_strips_common_forbidden_import_boilerplate() -> None:
    plan = parse_invoice_analytics_plan(
        '{"analysis_code":"import   pandas   as   pd\\nfrom   datetime   import   datetime\\ncurrent_date = datetime.strptime(\\\"2026-06-17\\\", \\\"%Y-%m-%d\\\")\\ndf = invoices_df.copy()\\nresult = {\\"summary\\": {\\"count\\": int(len(df))}, \\"tables\\": {}, \\"warnings\\": [], \\"answer_hints\\": []}","answer_language":"uk","reasoning_summary":"count invoices"}'
    )

    assert 'import pandas' not in plan.analysis_code
    assert 'from datetime' not in plan.analysis_code
    assert 'datetime.strptime' not in plan.analysis_code
    assert plan.analysis_code.startswith('df = invoices_df.copy()')
    validate_analytics_code(plan.analysis_code)


@pytest.mark.parametrize(
    'forbidden_import',
    [
        'import os',
        'import sys',
        'from pathlib import Path',
        'from subprocess import run',
        'import pandas',
        'import pandas as something_else',
        'from datetime import date',
        'from datetime import timedelta',
    ],
)
def test_invoice_analytics_plan_keeps_forbidden_imports_for_executor_rejection(forbidden_import: str) -> None:
    plan = parse_invoice_analytics_plan(
        '{"analysis_code":"'
        + forbidden_import.replace('\\', '\\\\').replace('"', '\\"')
        + '\\ndf = invoices_df.copy()\\nresult = {\\"summary\\": {\\"count\\": int(len(df))}, \\"tables\\": {}, \\"warnings\\": [], \\"answer_hints\\": []}","answer_language":"uk","reasoning_summary":"count invoices"}'
    )

    assert forbidden_import in plan.analysis_code
    with pytest.raises(AnalyticsCodeValidationError):
        validate_analytics_code(plan.analysis_code)


def test_invoice_analytics_plan_rejects_sqlite_import_at_planner_boundary() -> None:
    with pytest.raises(InvoiceAnalyticsPlanError):
        parse_invoice_analytics_plan(
            '{"analysis_code":"import sqlite3\\ndf = invoices_df.copy()\\nresult = {\\"summary\\": {\\"count\\": int(len(df))}, \\"tables\\": {}, \\"warnings\\": [], \\"answer_hints\\": []}","answer_language":"uk","reasoning_summary":"count invoices"}'
        )


def test_invoice_analytics_plan_removed_datetime_import_does_not_make_later_datetime_use_safe() -> None:
    plan = parse_invoice_analytics_plan(
        '{"analysis_code":"from datetime import datetime\\ndf = invoices_df.copy()\\nvalue = datetime.now()\\nresult = {\\"summary\\": {\\"value\\": str(value)}, \\"tables\\": {}, \\"warnings\\": [], \\"answer_hints\\": []}","answer_language":"uk","reasoning_summary":"unsafe datetime use"}'
    )

    assert 'from datetime import datetime' not in plan.analysis_code
    assert 'datetime.now()' in plan.analysis_code
    with pytest.raises(AnalyticsCodeValidationError):
        validate_analytics_code(plan.analysis_code)


@pytest.mark.parametrize(
    'raw',
    [
        '```json\n{"analysis_code":"result = {}"}\n```',
        '{"answer_language":"sk"}',
        '{"analysis_code":"df = invoices_df.copy()\\nrows = pd.read_sql(\\"SELECT * FROM invoice\\", None)\\nresult = {}"}',
        '{"analysis_code":"df = invoices_df.copy()\\nsummary = {}"}',
        '[]',
    ],
)
def test_invalid_invoice_analytics_plan_is_rejected(raw: str) -> None:
    with pytest.raises(InvoiceAnalyticsPlanError):
        parse_invoice_analytics_plan(raw)
