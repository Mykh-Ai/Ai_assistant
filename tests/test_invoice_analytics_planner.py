import pytest

from bot.services.invoice_analytics_planner import (
    InvoiceAnalyticsPlanError,
    parse_invoice_analytics_plan,
)


def test_valid_invoice_analytics_plan_is_accepted() -> None:
    plan = parse_invoice_analytics_plan(
        '{"analysis_code":"df = invoices_df.copy()\\nresult = {\\"summary\\": {\\"count\\": int(len(df))}, \\"tables\\": {}, \\"warnings\\": [], \\"answer_hints\\": []}","answer_language":"uk","reasoning_summary":"count invoices"}'
    )

    assert 'invoices_df.copy()' in plan.analysis_code
    assert plan.answer_language == 'uk'
    assert plan.reasoning_summary == 'count invoices'


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
