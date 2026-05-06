import asyncio
from types import SimpleNamespace

from bot.services import speech_to_text


def test_transcribe_audio_sends_multilingual_domain_context_prompt(tmp_path, monkeypatch):
    audio_path = tmp_path / 'voice.ogg'
    audio_path.write_bytes(b'fake audio')
    captured = {}

    class FakeTranscriptions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(text='prepísaný text')

    class FakeClient:
        def __init__(self, api_key):
            captured['api_key'] = api_key
            self.audio = SimpleNamespace(transcriptions=FakeTranscriptions())

    monkeypatch.setattr(speech_to_text, 'AsyncOpenAI', FakeClient)

    result = asyncio.run(
        speech_to_text.transcribe_audio(audio_path, 'test-key', 'gpt-4o-mini-transcribe')
    )

    assert result == 'prepísaný text'
    assert captured['api_key'] == 'test-key'
    assert captured['model'] == 'gpt-4o-mini-transcribe'
    assert captured['file'].name == str(audio_path)

    prompt = captured['prompt']
    assert 'Slovak, Ukrainian, Russian, English' in prompt
    assert 'mixed Surzhyk' in prompt
    assert 'Do not assume Portuguese, Vietnamese' in prompt
    assert 'Do not translate' in prompt
    assert 'Do not infer missing words' in prompt
    assert 'do not add words that were not spoken' in prompt
    assert 'зроби faktúru pre Tech Company za opravy' in prompt


def test_stt_context_prompt_is_not_a_canonical_action_router():
    prompt = speech_to_text.STT_CONTEXT_PROMPT

    assert 'canonical_action' not in prompt
    assert 'allowed_actions' not in prompt
    assert 'show_supplier_profile' not in prompt
    assert 'edit_supplier' not in prompt
    assert 'add_receipt' not in prompt
    assert 'delete_user_database' not in prompt
