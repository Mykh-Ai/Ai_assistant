from pathlib import Path

from openai import AsyncOpenAI


STT_CONTEXT_PROMPT = (
    'This is a short Telegram voice message for FakturaBot / OfficeFlow, '
    'a Slovak invoicing and small-business document bot. '
    'Expected spoken languages are Slovak, Ukrainian, Russian, English, '
    'or mixed Surzhyk / mixed Slovak-Ukrainian-Russian-English speech. '
    'The speaker may mix languages inside one sentence. '
    'Do not assume Portuguese, Vietnamese, or other unrelated languages when the audio is unclear. '
    'Transcribe what was spoken. Do not translate, do not summarize, '
    'and do not convert the message into a command. '
    'Do not infer missing words, do not correct the user intent, '
    'and do not add words that were not spoken. '
    'Preserve mixed-language wording, company names, invoice numbers, amounts, dates, '
    'and business terms. '
    'Common domain vocabulary may include Slovak words such as faktúra, bloček, doklad, '
    'profil, údaje, firma, dodávateľ, odberateľ, IČO, DIČ, IČ DPH, IBAN, áno, nie, '
    'schváliť, upraviť, zrušiť. '
    'It may also include Ukrainian or Russian words such as фактура, рахунок, чек, '
    'документи, профіль, реквізити, дані, компанія, фірма, постачальник, замовник, '
    'так, ні, да, нет, підтвердити, змінити, скасувати. '
    'It may also include English words, company names, service descriptions, '
    'or technical terms such as invoice, receipt, document, profile, company, service, '
    'repair, maintenance, support, development, hosting. '
    'Mixed speech examples may sound like: "зроби faktúru pre Tech Company za opravy", '
    '"покажи moje údaje", "додай bloček", "schváliť faktúru".'
)


async def transcribe_audio(file_path: Path, api_key: str, model: str) -> str:
    client = AsyncOpenAI(api_key=api_key)
    with open(file_path, 'rb') as f:
        response = await client.audio.transcriptions.create(
            model=model,
            file=f,
            prompt=STT_CONTEXT_PROMPT,
        )
    return response.text
