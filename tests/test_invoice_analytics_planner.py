import asyncio
import json
from types import SimpleNamespace

import pytest

from bot.services.invoice_analytics_planner import (
    InvoiceAnalyticsPlanError,
    parse_invoice_analytics_plan,
    plan_invoice_analytics_code,
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


class _PlannerOpenAICompletionsFake:
    last_kwargs: dict | None = None

    async def create(self, **kwargs):
        _PlannerOpenAICompletionsFake.last_kwargs = kwargs
        content = json.dumps(
            {
                'analysis_code': (
                    'df = invoices_df.copy()\n'
                    'result = {"summary": {"count": int(len(df))}, "tables": {}, "warnings": [], "answer_hints": []}'
                ),
                'answer_language': 'uk',
                'reasoning_summary': 'count invoices',
            }
        )
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class _PlannerOpenAIChatFake:
    def __init__(self) -> None:
        self.completions = _PlannerOpenAICompletionsFake()


class _PlannerOpenAIFake:
    def __init__(self, **kwargs) -> None:
        self.chat = _PlannerOpenAIChatFake()


def test_invoice_analytics_planner_prompt_declares_python_owned_runtime_policy(monkeypatch) -> None:
    _PlannerOpenAICompletionsFake.last_kwargs = None
    monkeypatch.setattr('bot.services.invoice_analytics_planner.AsyncOpenAI', _PlannerOpenAIFake)

    plan = asyncio.run(
        plan_invoice_analytics_code(
            user_question='Скільки фактур чекає оплати?',
            current_date_iso='2026-06-18',
            data_catalog={'datasets': {'invoices_df': {'columns': ['payment_status_canonical']}}},
            api_key='sk-test',
            model='gpt-4o',
        )
    )

    assert plan.answer_language == 'uk'
    assert _PlannerOpenAICompletionsFake.last_kwargs is not None
    system_prompt = _PlannerOpenAICompletionsFake.last_kwargs['messages'][0]['content']
    assert 'pd is already available' in system_prompt
    assert 'current_date is already available' in system_prompt
    assert 'do not import pandas' in system_prompt
    assert 'do not import datetime' in system_prompt
    assert 'do not redefine current_date' in system_prompt
    assert 'df = invoices_df.copy()' in system_prompt
    assert 'Assign the final JSON-serializable dict to variable result' in system_prompt
    assert 'Final user-facing business answer language is controlled by Python' in system_prompt
    assert 'Mandatory internal workflow before writing analysis_code' in system_prompt
    assert 'translate or normalize the user question into Slovak FakturaBot business semantics' in system_prompt
    assert 'identify the analysis kind' in system_prompt
    assert 'identify the exact period' in system_prompt
    assert 'choose the date column' in system_prompt
    assert 'identify row filters' in system_prompt
    assert 'identify only the required invoices_df columns' in system_prompt
    assert 'self-check that the code answers the normalized question' in system_prompt
    assert 'reasoning_summary' in system_prompt
    assert 'current_date.year' in system_prompt
    assert 'pd.to_datetime' in system_prompt
    assert '.dt.month.isin' in system_prompt
    assert 'For totals across currencies, group by currency' in system_prompt
    assert 'If repair_feedback is provided' in system_prompt


def test_invoice_analytics_planner_passes_repair_feedback_to_model(monkeypatch) -> None:
    _PlannerOpenAICompletionsFake.last_kwargs = None
    monkeypatch.setattr('bot.services.invoice_analytics_planner.AsyncOpenAI', _PlannerOpenAIFake)

    asyncio.run(
        plan_invoice_analytics_code(
            user_question='Koľko faktúr mám v máji?',
            current_date_iso='2026-06-18',
            data_catalog={'datasets': {'invoices_df': {'columns': ['issue_date', 'total_amount']}}},
            api_key='sk-test',
            model='gpt-4o',
            repair_feedback={
                'stage': 'execution',
                'error_type': 'AnalyticsCodeValidationError',
                'error_reason': 'name_not_allowed:datetime',
                'previous_analysis_code': 'df = invoices_df.copy()\nvalue = datetime.now()\nresult = {}',
            },
        )
    )

    assert _PlannerOpenAICompletionsFake.last_kwargs is not None
    user_payload = json.loads(_PlannerOpenAICompletionsFake.last_kwargs['messages'][1]['content'])
    assert user_payload['repair_feedback']['stage'] == 'execution'
    assert user_payload['repair_feedback']['error_reason'] == 'name_not_allowed:datetime'
    assert 'datetime.now()' in user_payload['repair_feedback']['previous_analysis_code']


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
