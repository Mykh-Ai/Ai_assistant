from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

_FINAL_ANSWER_LANGUAGE = 'sk'


async def answer_accounting_document_analytics(
    *,
    user_question: str,
    current_date_iso: str,
    computed_result: dict[str, Any],
    dataset_metadata: dict[str, Any],
    api_key: str | None,
    model: str,
    answer_language: str = 'sk',
) -> str:
    final_answer_language = _normalize_final_answer_language(answer_language)
    if api_key and api_key.startswith('sk-'):
        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You write the final user-facing answer for OfficeFlow/FakturaBot accounting document analytics. '
                            'Use only the provided computed_result and dataset_metadata. '
                            'The dataset contains confirmed receipts/bloceky and incoming invoices/prijate faktury for the current workspace only. '
                            'Do not invent numbers, vendors, categories, tax conclusions, VAT reports, bank settlement, accounting advice, or unsupported capabilities. '
                            'If result is empty, say that no matching confirmed accounting documents were found. '
                            'Answer in Slovak business language. Do not mirror Ukrainian, Russian, or mixed user input. '
                            'Keep the answer concise and professional. '
                            'Mention that this is read-only expense-document analytics when relevant.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {
                                'user_question': user_question,
                                'current_date_iso': current_date_iso,
                                'final_answer_language': final_answer_language,
                                'dataset_metadata': dataset_metadata,
                                'computed_result': computed_result,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            answer = (response.choices[0].message.content or '').strip()
            if answer:
                return answer
        except Exception:
            pass
    return build_accounting_document_analytics_fallback_answer(
        computed_result,
        dataset_metadata=dataset_metadata,
    )


def _normalize_final_answer_language(_answer_language: str | None) -> str:
    return _FINAL_ANSWER_LANGUAGE


def build_accounting_document_analytics_fallback_answer(
    computed_result: dict[str, Any],
    *,
    dataset_metadata: dict[str, Any] | None = None,
) -> str:
    summary = computed_result.get('summary') if isinstance(computed_result, dict) else None
    tables = computed_result.get('tables') if isinstance(computed_result, dict) else None
    warnings = computed_result.get('warnings') if isinstance(computed_result, dict) else None
    hints = computed_result.get('answer_hints') if isinstance(computed_result, dict) else None

    lines = ['Výsledok read-only analýzy bločkov a prijatých faktúr:']
    if isinstance(summary, dict) and summary:
        for key, value in summary.items():
            lines.append(f'- {key}: {_format_value(value)}')
    elif dataset_metadata and int(dataset_metadata.get('row_count') or 0) == 0:
        lines.append('- Vo vašom účte som nenašiel žiadne potvrdené bločky ani prijaté faktúry.')
    else:
        lines.append('- Výpočet nevrátil súhrnné hodnoty.')

    if isinstance(tables, dict) and tables:
        for table_name, rows in tables.items():
            if not rows:
                continue
            lines.append('')
            lines.append(f'{table_name}:')
            if isinstance(rows, list):
                for row in rows[:10]:
                    lines.append(f'- {_format_value(row)}')
            else:
                lines.append(f'- {_format_value(rows)}')

    all_warnings = []
    if isinstance(warnings, list):
        all_warnings.extend(str(item) for item in warnings if item)
    if isinstance(hints, list):
        all_warnings.extend(str(item) for item in hints if item)
    if all_warnings:
        lines.append('')
        lines.append('Poznámky:')
        for warning in all_warnings[:5]:
            lines.append(f'- {warning}')
    return '\n'.join(lines)


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f'{value:.2f}'
    if isinstance(value, dict):
        return ', '.join(f'{key}={_format_value(item)}' for key, item in value.items())
    if isinstance(value, list):
        return '; '.join(_format_value(item) for item in value)
    return str(value)
