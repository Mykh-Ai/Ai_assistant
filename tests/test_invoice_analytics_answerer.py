import asyncio
import json
from types import SimpleNamespace

from bot.services.invoice_analytics_answerer import answer_invoice_analytics


class _AnswerOpenAICompletionsFake:
    last_kwargs: dict | None = None

    async def create(self, **kwargs):
        _AnswerOpenAICompletionsFake.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='Mate 1 fakturu v sume 300.00 EUR.'))]
        )


class _AnswerOpenAIChatFake:
    def __init__(self) -> None:
        self.completions = _AnswerOpenAICompletionsFake()


class _AnswerOpenAIFake:
    def __init__(self, **kwargs) -> None:
        self.chat = _AnswerOpenAIChatFake()


def test_invoice_analytics_answerer_forces_slovak_business_language(monkeypatch) -> None:
    _AnswerOpenAICompletionsFake.last_kwargs = None
    monkeypatch.setattr('bot.services.invoice_analytics_answerer.AsyncOpenAI', _AnswerOpenAIFake)

    answer = asyncio.run(
        answer_invoice_analytics(
            user_question='Скільки фактур чекає оплати?',
            current_date_iso='2026-06-18',
            computed_result={
                'summary': {'invoice_count': 1, 'total': 300.0},
                'tables': {},
                'warnings': [],
                'answer_hints': [],
            },
            dataset_metadata={'row_count': 1, 'scope': 'outgoing_invoices_current_supplier_only'},
            api_key='sk-test',
            model='gpt-4o',
            answer_language='uk',
        )
    )

    assert answer == 'Mate 1 fakturu v sume 300.00 EUR.'
    assert _AnswerOpenAICompletionsFake.last_kwargs is not None
    messages = _AnswerOpenAICompletionsFake.last_kwargs['messages']
    system_prompt = messages[0]['content']
    user_payload = json.loads(messages[1]['content'])
    assert 'Answer in Slovak business language' in system_prompt
    assert 'Do not mirror Ukrainian, Russian, or mixed user input' in system_prompt
    assert user_payload['final_answer_language'] == 'sk'
    assert 'answer_language' not in user_payload
