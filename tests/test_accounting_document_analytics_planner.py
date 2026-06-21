import json

import pytest

from bot.services.accounting_document_analytics_dataset import build_accounting_document_analytics_data_catalog
from bot.services.accounting_document_analytics_planner import (
    AccountingDocumentAnalyticsPlanError,
    parse_accounting_document_analytics_plan,
    plan_accounting_document_analytics_code,
)


def test_parse_accounting_document_analytics_plan_accepts_sandbox_code() -> None:
    plan = parse_accounting_document_analytics_plan(
        json.dumps(
            {
                'analysis_code': "df = accounting_documents_df.copy()\nresult = {'summary': {'count': len(df)}}",
                'answer_language': 'uk',
                'reasoning_summary': 'Pocet potvrdenych dokladov.',
            }
        )
    )

    assert 'accounting_documents_df.copy()' in plan.analysis_code
    assert plan.answer_language == 'uk'
    assert plan.reasoning_summary == 'Pocet potvrdenych dokladov.'


def test_parse_accounting_document_analytics_plan_strips_harmless_import_boilerplate() -> None:
    plan = parse_accounting_document_analytics_plan(
        json.dumps(
            {
                'analysis_code': (
                    'import pandas as pd\n'
                    'from datetime import datetime\n'
                    "current_date = datetime.strptime('2026-06-21', '%Y-%m-%d')\n"
                    "df = accounting_documents_df.copy()\n"
                    "result = {'summary': {'count': len(df)}}"
                )
            }
        )
    )

    assert 'import pandas' not in plan.analysis_code
    assert 'datetime.strptime' not in plan.analysis_code
    assert plan.analysis_code.startswith('df = accounting_documents_df.copy()')


@pytest.mark.parametrize(
    'analysis_code',
    [
        'SELECT * FROM accounting_documents',
        "df = pd.read_sql('select * from x', conn)\nresult = {}",
        'import sqlite3\nresult = {}',
    ],
)
def test_parse_accounting_document_analytics_plan_rejects_sql_and_db_text(analysis_code: str) -> None:
    with pytest.raises(AccountingDocumentAnalyticsPlanError):
        parse_accounting_document_analytics_plan(json.dumps({'analysis_code': analysis_code}))


def test_parse_accounting_document_analytics_plan_rejects_markdown_fences() -> None:
    with pytest.raises(AccountingDocumentAnalyticsPlanError):
        parse_accounting_document_analytics_plan(
            json.dumps({'analysis_code': "```python\nresult = {}\n```"})
        )


def test_accounting_document_analytics_planner_prompt_is_bounded(monkeypatch) -> None:
    captured: dict = {}

    class _FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)

            class _Message:
                content = json.dumps(
                    {
                        'analysis_code': "df = accounting_documents_df.copy()\nresult = {'summary': {'count': len(df)}}",
                        'answer_language': 'sk',
                        'reasoning_summary': 'Pocet.',
                    }
                )

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    class _FakeClient:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': _FakeCompletions()})()

    monkeypatch.setattr('bot.services.accounting_document_analytics_planner.AsyncOpenAI', _FakeClient)

    import asyncio

    plan = asyncio.run(
        plan_accounting_document_analytics_code(
            user_question='Koľko som minul v BAUHAUS?',
            current_date_iso='2026-06-21',
            data_catalog=build_accounting_document_analytics_data_catalog(),
            api_key='sk-test',
            model='gpt-test',
        )
    )

    assert plan.analysis_code
    system_prompt = captured['messages'][0]['content']
    assert 'accounting_documents_df' in system_prompt
    assert 'Allowed variables: accounting_documents_df, pd, current_date.' in system_prompt
    assert 'No bank movements or bank matching.' in json.dumps(captured['messages'][1]['content'])
    assert 'do not import pandas' in system_prompt
    assert 'tax' in system_prompt.lower()


def test_accounting_document_analytics_planner_prompt_carries_category_filter_hints(monkeypatch, tmp_path) -> None:
    captured: dict = {}

    class _FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)

            class _Message:
                content = json.dumps(
                    {
                        'analysis_code': (
                            "df = accounting_documents_df.copy()\n"
                            "df = df[df['category_id'] == 'vehicle_fuel']\n"
                            "result = {'summary': {'total': float(df['total_amount'].sum())}, 'tables': {}, 'warnings': [], 'answer_hints': []}"
                        ),
                        'answer_language': 'sk',
                        'reasoning_summary': 'Palivo podla category_id.',
                    }
                )

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    class _FakeClient:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': _FakeCompletions()})()

    monkeypatch.setattr('bot.services.accounting_document_analytics_planner.AsyncOpenAI', _FakeClient)

    import asyncio

    plan = asyncio.run(
        plan_accounting_document_analytics_code(
            user_question='Скільки я витратив на пальне в березні?',
            current_date_iso='2026-06-21',
            data_catalog=build_accounting_document_analytics_data_catalog(
                storage_dir=tmp_path,
                workspace_key='telegram-111',
                user_question='Скільки я витратив на пальне в березні?',
            ),
            api_key='sk-test',
            model='gpt-test',
        )
    )

    payload = json.loads(captured['messages'][1]['content'])
    assert payload['data_catalog']['category_filter_hints'][0]['category_id'] == 'vehicle_fuel'
    assert 'vehicle_fuel' in plan.analysis_code
    assert 'Use category_id as the primary category filter' in captured['messages'][0]['content']


def test_accounting_document_analytics_planner_rejects_plan_missing_python_category_hint(monkeypatch, tmp_path) -> None:
    class _FakeCompletions:
        async def create(self, **kwargs):
            class _Message:
                content = json.dumps(
                    {
                        'analysis_code': (
                            "df = accounting_documents_df.copy()\n"
                            "df = df[df['category_label'].str.lower() == 'pohonné látky']\n"
                            "result = {'summary': {'total': float(df['total_amount'].sum())}, 'tables': {}, 'warnings': [], 'answer_hints': []}"
                        ),
                        'answer_language': 'sk',
                        'reasoning_summary': 'Wrong invented label.',
                    }
                )

            class _Choice:
                message = _Message()

            class _Response:
                choices = [_Choice()]

            return _Response()

    class _FakeClient:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': _FakeCompletions()})()

    monkeypatch.setattr('bot.services.accounting_document_analytics_planner.AsyncOpenAI', _FakeClient)

    import asyncio

    with pytest.raises(AccountingDocumentAnalyticsPlanError, match='missing_required_category_id_filter_column'):
        asyncio.run(
            plan_accounting_document_analytics_code(
                user_question='Скільки я витратив на пальне в березні?',
                current_date_iso='2026-06-21',
                data_catalog=build_accounting_document_analytics_data_catalog(
                    storage_dir=tmp_path,
                    workspace_key='telegram-111',
                    user_question='Скільки я витратив на пальне в березні?',
                ),
                api_key='sk-test',
                model='gpt-test',
            )
        )
