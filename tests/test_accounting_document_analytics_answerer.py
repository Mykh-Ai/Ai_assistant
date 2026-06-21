from bot.services.accounting_document_analytics_answerer import build_accounting_document_analytics_fallback_answer


def test_accounting_document_analytics_fallback_answer_is_slovak_and_read_only() -> None:
    answer = build_accounting_document_analytics_fallback_answer(
        {
            'summary': {'count': 2, 'total': 113.83},
            'tables': {'by_category': [{'category_label': 'Material', 'total_amount': 113.83}]},
            'warnings': [],
            'answer_hints': ['Použité sú iba potvrdené doklady.'],
        },
        dataset_metadata={'row_count': 2},
    )

    assert 'read-only' in answer
    assert 'bločkov a prijatých faktúr' in answer
    assert 'count: 2' in answer
    assert 'total: 113.83' in answer
    assert 'Použité sú iba potvrdené doklady.' in answer


def test_accounting_document_analytics_fallback_answer_handles_empty_dataset() -> None:
    answer = build_accounting_document_analytics_fallback_answer({}, dataset_metadata={'row_count': 0})

    assert 'nenašiel žiadne potvrdené bločky ani prijaté faktúry' in answer
