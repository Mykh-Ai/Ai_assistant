import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import process_invoice_postpdf_decision, process_invoice_preview_confirmation, process_invoice_text
from bot.services.semantic_action_resolver import resolve_semantic_action


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.message_id = 1
        self.update_id = 1
        self.from_user = None
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


class _DummyDecisionState:
    def __init__(self) -> None:
        self.data = {'last_invoice_id': 999}
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
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


def test_top_level_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='витворить фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='сделай фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='upraviť fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pošli fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'send_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='blabla',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_invoice_create_not_misrouted_to_add_contact_when_company_mentioned() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre company ZS',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'


def test_state_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='potvrdzujem',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='cancel',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'nie'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_postpdf_decision',
            allowed_actions=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='подтвердить',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


def test_unknown_top_level_stops_flow(tmp_path: Path) -> None:
    message = _DummyMessage('blabla')
    state = _DummyState()
    asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text='blabla'))
    assert state.cleared is True
    assert 'Nerozumiem požadovanej akcii' in message.answers[-1]


def test_preview_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('maybe')
    state = _DummyState()
    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=_config(tmp_path),
            confirmation_text='maybe',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte áno alebo nie.'


def test_postpdf_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('later')
    state = _DummyDecisionState()
    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=_config(tmp_path),
            decision_text='later',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'
