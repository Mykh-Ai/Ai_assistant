from __future__ import annotations

import asyncio

from bot.handlers.onboarding import OnboardingStates, onboarding_email


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.current_state = OnboardingStates.email
        self.data: dict[str, object] = {}

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state


def test_onboarding_email_goes_directly_to_due_days_without_smtp_prompts() -> None:
    message = _DummyMessage('supplier@example.com')
    state = _DummyState()

    asyncio.run(onboarding_email(message, state))

    assert state.current_state == OnboardingStates.days_due
    assert state.data['email'] == 'supplier@example.com'
    assert message.answers[-1] == '9/9 Zadajte štandardnú splatnosť v dňoch (celé číslo > 0):'
    assert 'SMTP' not in '\n'.join(message.answers)
