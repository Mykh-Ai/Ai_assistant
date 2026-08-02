import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import (
    InvoiceReferenceContinuationStates,
    invoice_reference_continuation,
    process_invoice_text,
)
from bot.services.db import init_db


class _Message:
    def __init__(self, text: str, telegram_id: int = 111) -> None:
        self.text = text
        self.message_id = 1
        self.from_user = type('User', (), {'id': telegram_id})()
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)

    async def answer_document(self, *args, **kwargs) -> None:
        return None


class _State:
    def __init__(self) -> None:
        self.current_state = None
        self.data: dict[str, object] = {}
        self.cleared = False

    async def get_state(self):
        return self.current_state

    async def set_state(self, value) -> None:
        self.current_state = getattr(value, 'state', value)

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()
        self.cleared = True


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def test_missing_invoice_reference_enters_real_continuation(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('Vymazať faktúru')
    state = _State()

    async def _resolver(**kwargs):
        return 'delete_existing_invoice'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == InvoiceReferenceContinuationStates.waiting_reference.state
    assert state.data['pending_invoice_reference_action'] == 'delete_existing_invoice'
    assert 'číslo faktúry' in message.answers[-1].casefold()


def test_next_reference_is_consumed_by_continuation_owner(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('10')
    state = _State()
    state.current_state = InvoiceReferenceContinuationStates.waiting_reference.state
    state.data = {
        'pending_invoice_reference_action': 'delete_existing_invoice',
        'pending_workspace_id': None,
        'source_channel': 'text',
    }
    calls: list[tuple[str, str]] = []

    async def _continue(**kwargs):
        calls.append((kwargs['action_id'], kwargs['invoice_reference']))

    monkeypatch.setattr('bot.handlers.invoice._execute_invoice_reference_action', _continue)
    asyncio.run(invoice_reference_continuation(message=message, state=state, config=config))

    assert calls == [('delete_existing_invoice', '10')]
    assert not any('Nerozumiem' in answer for answer in message.answers)


def test_callback_message_adapter_uses_human_actor_and_source_chat() -> None:
    from bot.handlers.decision_callbacks import _CallbackMessageAdapter

    human = type('Human', (), {'id': 111})()
    bot_author = type('BotAuthor', (), {'id': 999, 'is_bot': True})()
    source_chat = type('Chat', (), {'id': 77})()
    source = type('Source', (), {'from_user': bot_author, 'chat': source_chat, 'message_id': 8})()
    callback = type('Callback', (), {'from_user': human, 'message': source})()

    adapter = _CallbackMessageAdapter(callback)

    assert adapter.from_user is human
    assert adapter.chat is source_chat
