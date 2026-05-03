from __future__ import annotations

import asyncio
from datetime import date

from bot.handlers.onboarding import (
    OnboardingStates,
    onboarding_email,
    onboarding_first_invoice_number,
)


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self, current_state=OnboardingStates.email) -> None:
        self.current_state = current_state
        self.data: dict[str, object] = {}

    async def get_data(self) -> dict[str, object]:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state


def test_onboarding_email_goes_to_first_invoice_number_without_smtp_prompts() -> None:
    message = _DummyMessage('supplier@example.com')
    state = _DummyState()

    asyncio.run(onboarding_email(message, state))

    issue_year = date.today().year
    assert state.current_state == OnboardingStates.first_invoice_number
    assert state.data['email'] == 'supplier@example.com'
    assert state.data['invoice_number_issue_year'] == issue_year
    assert f'{issue_year}0001' in message.answers[-1]
    assert 'SMTP' not in '\n'.join(message.answers)


def test_onboarding_first_invoice_number_goes_to_due_days_without_smtp_prompts() -> None:
    issue_year = date.today().year
    message = _DummyMessage(f'{issue_year}0025')
    state = _DummyState(OnboardingStates.first_invoice_number)
    state.data['invoice_number_issue_year'] = issue_year

    asyncio.run(onboarding_first_invoice_number(message, state))

    assert state.current_state == OnboardingStates.days_due
    assert state.data['first_invoice_number'] == f'{issue_year}0025'
    assert message.answers[-1] == '10/10 Zadajte štandardnú splatnosť v dňoch (celé číslo > 0):'
    assert 'SMTP' not in '\n'.join(message.answers)
