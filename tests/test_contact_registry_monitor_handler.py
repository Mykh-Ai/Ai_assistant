from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers import contact_registry_monitor as handler
from bot.services.contact_registry_monitor import ProposalResolution
from bot.services.decision_resolver import resolve_yes_no


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='test',
        openai_api_key=None,
        openai_stt_model='gpt-test',
        openai_llm_model='gpt-test',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path / 'storage',
    )


class _Message:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.cleared = False

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def edit_reply_markup(self, *, reply_markup) -> None:
        self.cleared = reply_markup is None


class _Callback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.from_user = type('User', (), {'id': 111})()
        self.message = _Message()
        self.callback_answers: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, *, show_alert: bool = False) -> None:
        self.callback_answers.append((text, show_alert))


def test_monitor_context_uses_shared_yes_no_resolver_without_llm() -> None:
    assert asyncio.run(
        resolve_yes_no(
            context_name='contact_registry_monitor_proposal',
            user_input_text='yes',
            api_key=None,
            model='gpt-test',
        )
    ) == 'yes'
    assert asyncio.run(
        resolve_yes_no(
            context_name='contact_registry_monitor_proposal',
            user_input_text='no',
            api_key=None,
            model='gpt-test',
        )
    ) == 'no'


def test_callback_dispatches_shared_resolver_result(monkeypatch, tmp_path: Path) -> None:
    seen: dict[str, str] = {}

    async def fake_resolver(**kwargs):
        seen['context'] = kwargs['context_name']
        seen['input'] = kwargs['user_input_text']
        return 'yes'

    class _Service:
        def __init__(self, db_path, config) -> None:
            pass

        def resolve(self, **kwargs):
            seen['decision'] = kwargs['decision']
            return ProposalResolution('applied', 'Tech Company s.r.o.')

    monkeypatch.setattr(handler, 'resolve_yes_no', fake_resolver)
    monkeypatch.setattr(handler, 'ContactRegistryMonitorService', _Service)
    callback = _Callback(
        'contact_monitor:yes:00000000-0000-4000-8000-000000000000'
    )

    asyncio.run(
        handler.contact_registry_monitor_callback(callback, _config(tmp_path))
    )

    assert seen == {
        'context': 'contact_registry_monitor_proposal',
        'input': 'yes',
        'decision': 'yes',
    }
    assert callback.message.cleared is True
    assert 'PDF' in callback.message.answers[0]
