from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from openai import AsyncOpenAI


class AccountingDocumentAnalyticsPlanError(ValueError):
    pass


@dataclass(frozen=True)
class AccountingDocumentAnalyticsPlan:
    analysis_code: str
    answer_language: str
    reasoning_summary: str


_FORBIDDEN_CODE_PATTERNS = (
    r'\bSELECT\b',
    r'\bINSERT\b',
    r'\bUPDATE\b',
    r'\bDELETE\b',
    r'\bDROP\b',
    r'\bsqlite3\b',
    r'\bread_sql\b',
)

_PLANNER_WORKFLOW_GUIDANCE = (
    'Mandatory internal workflow before writing analysis_code: '
    '1) normalize the user question into Slovak OfficeFlow accounting-document semantics; '
    '2) decide whether the user asks about expense-side documents, not outgoing invoices; '
    '3) identify analysis kind: sum, count, list, comparison, grouping, average, or top ranking; '
    '4) identify the exact period: explicit year, current year, month/months, date range, relative period, or unknown; '
    '5) choose the date column: issue_date by default, tax_date for tax/delivery-date wording, due_date for due-date/splatnost wording; '
    '6) identify row filters such as document_type, vendor_name, category_id/category_label, currency, month numbers, years, or date range; '
    '7) identify only required accounting_documents_df columns from the data catalog; '
    '8) write sandbox-safe pandas code; '
    '9) self-check that the code answers the normalized question and that result contains facts needed for the final Slovak business answer. '
    'If the period, vendor, category, or document type is genuinely ambiguous, do not invent it; return result warnings/answer_hints asking for clarification. '
    'Put a short Slovak normalized plan in reasoning_summary, including analysis_kind, period, date_column, filters, and output facts.'
)

_PERIOD_AND_DATE_GUIDANCE = (
    'Date filtering rules are strict. issue_date, tax_date, and due_date are ISO date strings; '
    'convert the selected date column with pd.to_datetime(..., errors="coerce") before using .dt.year, .dt.month, comparisons, or ranges. '
    'Use current_date for today, this month, this year, previous periods, and any missing current-year default. '
    'If the user names a month but no year, use int(current_date.year) as the target year. '
    'Never filter date columns by translated month-name text and never assume day 1; use numeric .dt.month and .dt.year. '
    'Recognize Slovak, Ukrainian, Russian, and common transliterated month names. '
    'For multiple named months, create a list of month numbers and use .dt.month.isin(...). '
    'For totals across currencies, group by currency; never merge different currencies into one amount.'
)

_SANDBOX_CODE_GUIDANCE = (
    'Sandbox rules: no imports; no SQL/DB access; no file/network/system calls; no writes; no eval, exec, compile, open, __import__; '
    'no os, sys, subprocess, socket, requests, pathlib, sqlite3, dunder access; '
    'no for/while loops, comprehensions, function definitions, class definitions, lambda, with, global, or nonlocal. '
    'Use vectorized pandas operations, boolean masks, groupby, agg, reset_index, round, to_dict(orient="records"), len, int, float, str, list, dict, and literals. '
    'Start by copying the dataframe exactly like this: df = accounting_documents_df.copy(). '
    'Assign the final JSON-serializable dict to variable result. '
    'Required result shape: {"summary": {...}, "tables": {...}, "warnings": [...], "answer_hints": [...]}.'
)


def parse_accounting_document_analytics_plan(raw_model_output: str) -> AccountingDocumentAnalyticsPlan:
    try:
        parsed = json.loads(raw_model_output or '{}')
    except json.JSONDecodeError as exc:
        raise AccountingDocumentAnalyticsPlanError('invalid_json') from exc
    if not isinstance(parsed, dict):
        raise AccountingDocumentAnalyticsPlanError('invalid_plan_shape')

    analysis_code = parsed.get('analysis_code')
    if not isinstance(analysis_code, str) or not analysis_code.strip():
        raise AccountingDocumentAnalyticsPlanError('missing_analysis_code')
    analysis_code = _normalize_planned_analysis_code(analysis_code)
    if '```' in analysis_code or '```' in raw_model_output:
        raise AccountingDocumentAnalyticsPlanError('markdown_fence_not_allowed')
    if not re.search(r'(^|\n)\s*result\s*=', analysis_code):
        raise AccountingDocumentAnalyticsPlanError('missing_result_assignment')
    if any(re.search(pattern, analysis_code, flags=re.IGNORECASE) for pattern in _FORBIDDEN_CODE_PATTERNS):
        raise AccountingDocumentAnalyticsPlanError('forbidden_sql_or_db_text')

    answer_language = parsed.get('answer_language')
    if not isinstance(answer_language, str) or not answer_language.strip():
        answer_language = 'sk'
    answer_language = answer_language.strip().lower()[:16]

    reasoning_summary = parsed.get('reasoning_summary')
    if not isinstance(reasoning_summary, str) or not reasoning_summary.strip():
        reasoning_summary = 'Analyze the provided accounting documents dataframe.'

    return AccountingDocumentAnalyticsPlan(
        analysis_code=analysis_code.strip(),
        answer_language=answer_language,
        reasoning_summary=reasoning_summary.strip()[:500],
    )


def _normalize_planned_analysis_code(code: str) -> str:
    normalized_lines: list[str] = []
    for line in code.splitlines():
        stripped = line.strip()
        if re.fullmatch(r'import\s+pandas\s+as\s+pd', stripped):
            continue
        if re.fullmatch(r'from\s+datetime\s+import\s+datetime', stripped):
            continue
        if re.fullmatch(r'current_date\s*=\s*datetime\.strptime\(.+\)', stripped):
            continue
        normalized_lines.append(line)
    return '\n'.join(normalized_lines).strip()


async def plan_accounting_document_analytics_code(
    *,
    user_question: str,
    current_date_iso: str,
    data_catalog: dict[str, Any],
    api_key: str | None,
    model: str,
    repair_feedback: dict[str, Any] | None = None,
) -> AccountingDocumentAnalyticsPlan:
    if not api_key or not api_key.startswith('sk-'):
        raise AccountingDocumentAnalyticsPlanError('missing_openai_api_key')

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={'type': 'json_object'},
        messages=[
            {
                'role': 'system',
                'content': (
                    'You are a bounded data analyst code planner for OfficeFlow/FakturaBot accounting document analytics. '
                    'Return strict JSON only with keys analysis_code, answer_language, reasoning_summary. '
                    'No markdown fences. The user may write Slovak, Ukrainian, Russian, or mixed language. '
                    'Final user-facing business answer language is controlled by Python; answer_language is metadata only. '
                    'You may write Python code only over the provided sanitized dataframe accounting_documents_df. '
                    'This dataframe contains confirmed expense-side receipts/bloceky and incoming invoices/prijate faktury. '
                    'It does not contain outgoing invoices, bank data, raw OCR, or storage paths. '
                    'Allowed variables: accounting_documents_df, pd, current_date. '
                    'pd is already available; do not import pandas. '
                    'current_date is already available from Python; do not import datetime, do not redefine current_date, and never assume the current year from memory. '
                    'Allowed analysis: counts, sums, grouping, period filters, vendor/category/document_type/currency filters, comparisons, limited lists, averages, and top rankings. '
                    + _PLANNER_WORKFLOW_GUIDANCE
                    + ' '
                    + _PERIOD_AND_DATE_GUIDANCE
                    + ' '
                    + _SANDBOX_CODE_GUIDANCE
                    + ' '
                    'Use category_id/category_label only as confirmed intake metadata, not as tax or accounting judgement. '
                    'If the question asks about outgoing invoices, bank movements, VAT/tax advice, accounting export, category creation, edit, delete, upload, sync, or any write action, return a result that refuses the unsupported/write request in warnings and answer_hints; do not perform a mutation. '
                    'If repair_feedback is provided, fix the previous failure and return a complete replacement analysis_code.'
                ),
            },
            {
                'role': 'user',
                'content': json.dumps(
                    {
                        'user_question': user_question,
                        'current_date_iso': current_date_iso,
                        'current_year': current_date_iso[:4],
                        'current_month': current_date_iso[5:7],
                        'current_day': current_date_iso[8:10],
                        'timezone_context': 'Europe/Bratislava/Europe/Berlin local runtime date unless configured otherwise',
                        'data_catalog': data_catalog,
                        'repair_feedback': repair_feedback or {},
                        'expected_json': {
                            'analysis_code': 'python code assigning result',
                            'answer_language': 'sk|uk|ru|mixed',
                            'reasoning_summary': 'short Slovak normalized plan with analysis_kind, period, date_column, filters, output facts',
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    raw = response.choices[0].message.content or '{}'
    return parse_accounting_document_analytics_plan(raw)
