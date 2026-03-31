from pathlib import Path

from openai import AsyncOpenAI


async def transcribe_audio(file_path: Path, api_key: str, model: str) -> str:
    client = AsyncOpenAI(api_key=api_key)
    with open(file_path, 'rb') as f:
        response = await client.audio.transcriptions.create(model=model, file=f)
    return response.text
