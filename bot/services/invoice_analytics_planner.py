from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from openai import AsyncOpenAI


class InvoiceAnalyticsPlanError(ValueError):
    pass


@dataclass(frozen=True)
class InvoiceAnalyticsPlan:
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


def parse_invoice_analytics_plan(raw_model_output: str) -> InvoiceAnalyticsPlan:
    try:
        parsed = json.loads(raw_model_output or '{}')
    except json.JSONDecodeError as exc:
        raise InvoiceAnalyticsPlanError('invalid_json') from exc
    if not isinstance(parsed, dict):
        raise InvoiceAnalyticsPlanError('invalid_plan_shape')

    analysis_code = parsed.get('analysis_code')
    if not isinstance(analysis_code, str) or not analysis_code.strip():
        raise InvoiceAnalyticsPlanError('missing_analysis_code')
    analysis_code = _normalize_planned_analysis_code(analysis_code)
    if '```' in analysis_code or '```' in raw_model_output:
        raise InvoiceAnalyticsPlanError('markdown_fence_not_allowed')
    if not re.search(r'(^|\n)\s*result\s*=', analysis_code):
        raise InvoiceAnalyticsPlanError('missing_result_assignment')
    if any(re.search(pattern, analysis_code, flags=re.IGNORECASE) for pattern in _FORBIDDEN_CODE_PATTERNS):
        raise InvoiceAnalyticsPlanError('forbidden_sql_or_db_text')

    answer_language = parsed.get('answer_language')
    if not isinstance(answer_language, str) or not answer_language.strip():
        answer_language = 'sk'
    answer_language = answer_language.strip().lower()[:16]

    reasoning_summary = parsed.get('reasoning_summary')
    if not isinstance(reasoning_summary, str) or not reasoning_summary.strip():
        reasoning_summary = 'Analyze the provided invoices dataframe.'

    return InvoiceAnalyticsPlan(
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


async def plan_invoice_analytics_code(
    *,
    user_question: str,
    current_date_iso: str,
    data_catalog: dict[str, Any],
    api_key: str | None,
    model: str,
) -> InvoiceAnalyticsPlan:
    if not api_key or not api_key.startswith('sk-'):
        raise InvoiceAnalyticsPlanError('missing_openai_api_key')

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={'type': 'json_object'},
        messages=[
            {
                'role': 'system',
                'content': (
                    'You are a bounded data analyst code planner for OfficeFlow/FakturaBot. '
                    'Return strict JSON only with keys analysis_code, answer_language, reasoning_summary. '
                    'No markdown fences. The user may write Slovak, Ukrainian, Russian, or mixed language. '
                    'You may write Python code only over the provided sanitized dataframe invoices_df. '
                    'The code must assign the final JSON-serializable dict to variable result. '
                    'Allowed variables: invoices_df, pd, current_date. '
                    'pd is already available; do not import pandas. '
                    'current_date is already available from Python; do not import datetime, do not redefine current_date, and never assume the current year from memory. '
                    'Start by copying the dataframe exactly like this: df = invoices_df.copy(). '
                    'Allowed analysis: counts, sums, grouping, period filters, payment_status_canonical/customer/currency filters, comparisons, limited lists. '
                    'Use payment_status_canonical for paid, pending payment, and overdue questions; do not treat invoice_status_raw as bank-confirmed payment truth. '
                    'Forbidden: imports, file/network/system calls, SQL, DB access, writes, eval, exec, compile, open, __import__, os, sys, subprocess, socket, requests, pathlib, sqlite3, dunder access. '
                    'Assign the final JSON-serializable dict to variable result. '
                    'Required result shape: {"summary": {...}, "tables": {...}, "warnings": [...], "answer_hints": [...]}. '
                    'If the question asks to edit, delete, send, mark paid, or otherwise mutate invoices, return a result that refuses the write request in warnings and answer_hints; do not perform a mutation.'
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
                        'expected_json': {
                            'analysis_code': 'python code assigning result',
                            'answer_language': 'sk|uk|ru|mixed',
                            'reasoning_summary': 'short explanation',
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    raw = response.choices[0].message.content or '{}'
    return parse_invoice_analytics_plan(raw)
