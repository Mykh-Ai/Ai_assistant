import json
from pathlib import Path

from openai import AsyncOpenAI


_PROMPT_PATH = Path(__file__).parent.parent.parent / 'prompts' / 'invoice_draft_prompt.txt'

_EMPTY_DRAFT: dict = {
    'customer_name': None,
    'item_name_raw': None,
    'quantity': None,
    'unit': None,
    'amount': None,
    'currency': None,
    'issue_date': None,
    'due_days': None,
}


async def parse_invoice_draft(text: str, api_key: str, model: str) -> dict:
    system_prompt = _PROMPT_PATH.read_text(encoding='utf-8')
    client = AsyncOpenAI(api_key=api_key)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text},
        ],
        response_format={'type': 'json_object'},
        temperature=0,
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    # ensure all expected keys are present, fill missing with None
    return {key: parsed.get(key) for key in _EMPTY_DRAFT}
