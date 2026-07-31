from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3

import pytest

from bot.config import Config
from bot.handlers import invoice
from bot.handlers.runtime_issue import (
    RUNTIME_ISSUE_FAILURE,
    RUNTIME_ISSUE_ACTION,
    cmd_runtime_issue,
    extract_runtime_issue_prefix_description,
    resolve_runtime_issue_intent,
)
from bot.services.runtime_issue import RuntimeIssueError
from bot.services import active_fsm_guard
from bot.services.db import init_db
from bot.services.info_help import build_product_truth_guidance
from bot.services.info_help import InfoHelpTriageResult
from bot.services.product_truth import get_capability, get_safe_answer_payload


ADMIN_ID = 111
USER_ID = 222


class _Message:
    def __init__(
        self,
        text: str,
        *,
        actor: int = ADMIN_ID,
        message_id: int = 31,
        chat_id: int = 41,
        fail_answer: bool = False,
    ) -> None:
        self.text = text
        self.from_user = type('User', (), {'id': actor})()
        self.chat = type('Chat', (), {'id': chat_id})()
        self.message_id = message_id
        self.answers: list[str] = []
        self.fail_answer = fail_answer

    async def answer(self, text: str, **kwargs) -> None:
        if self.fail_answer:
            raise RuntimeError('telegram unavailable')
        self.answers.append(text)


class _State:
    def __init__(self, current: str | None = None, data: dict | None = None) -> None:
        self.current = current
        self.data = dict(data or {})
        self.set_calls = 0
        self.clear_calls = 0
        self.update_calls = 0

    async def get_state(self) -> str | None:
        return self.current

    async def get_data(self) -> dict:
        return dict(self.data)

    async def set_state(self, state) -> None:
        self.set_calls += 1
        self.current = state.state if hasattr(state, 'state') else state

    async def update_data(self, **kwargs) -> None:
        self.update_calls += 1
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.clear_calls += 1
        self.current = None
        self.data.clear()


def _config(tmp_path: Path, *, admins: frozenset[int] = frozenset({ADMIN_ID})) -> Config:
    config = Config(
        bot_token='token',
        openai_api_key='fake-key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'routes.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset({ADMIN_ID, USER_ID}),
        admin_telegram_user_ids=admins,
    )
    init_db(config.db_path)
    return config


def _count(config: Config) -> int:
    with sqlite3.connect(config.db_path) as connection:
        return int(connection.execute(
            'SELECT count(*) FROM runtime_issues'
        ).fetchone()[0])


def _row(config: Config) -> sqlite3.Row:
    with sqlite3.connect(config.db_path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            'SELECT issue_id, actor_telegram_id, telegram_update_id, '
            'telegram_message_id, telegram_chat_id, workspace_id, source_channel, '
            'active_fsm_state, active_fsm_context_summary_json, description '
            'FROM runtime_issues'
        ).fetchone()
    assert row is not None
    return row


def test_exact_command_and_bare_command_use_same_message_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    state = _State()
    message = _Message('/issue Po potvrdení sa správa vôbec nezobrazila.')

    asyncio.run(
        cmd_runtime_issue(
            message,
            state,
            config,
            type('Update', (), {'update_id': 501})(),
        )
    )
    assert _count(config) == 1
    assert 'Problém som uložil ako IR-' in message.answers[-1]
    assert 'nepotvrdzuje' in message.answers[-1]
    assert 'opravu' in message.answers[-1]
    assert state.set_calls == state.clear_calls == state.update_calls == 0

    bare = _Message('/issue', message_id=32)
    asyncio.run(
        cmd_runtime_issue(
            bare,
            state,
            config,
            type('Update', (), {'update_id': 502})(),
        )
    )
    assert _count(config) == 1
    assert '/issue' in bare.answers[-1]
    assert state.set_calls == state.clear_calls == state.update_calls == 0


@pytest.mark.parametrize(
    'technical_error',
    [
        sqlite3.OperationalError('admin database unavailable'),
        OSError('admin database read failed'),
    ],
)
def test_idle_exact_command_admin_check_failure_is_truthful_and_preserves_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    technical_error: Exception,
) -> None:
    config = _config(tmp_path)
    state = _State()
    message = _Message('/issue Po potvrdení sa správa nezobrazila.')

    def _fail_admin_check(*args, **kwargs):
        raise technical_error

    monkeypatch.setattr(
        'bot.handlers.runtime_issue.is_admin_telegram_user',
        _fail_admin_check,
    )
    asyncio.run(
        cmd_runtime_issue(
            message,
            state,
            config,
            type('Update', (), {'update_id': 551})(),
        )
    )

    assert message.answers == [RUNTIME_ISSUE_FAILURE]
    assert _count(config) == 0
    assert state.current is None
    assert state.data == {}
    assert state.set_calls == state.clear_calls == state.update_calls == 0


@pytest.mark.parametrize(
    'technical_error',
    [
        sqlite3.OperationalError('admin database unavailable'),
        OSError('admin database read failed'),
    ],
)
def test_active_exact_command_admin_check_failure_is_handled_without_business_fallthrough(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    technical_error: Exception,
) -> None:
    config = _config(tmp_path)
    protected = {'invoice_draft': {'customer': 'Alfa'}}
    state = _State('InvoiceStates:waiting_input', protected)
    message = _Message('/issue Po potvrdení sa správa nezobrazila.')

    def _fail_admin_check(*args, **kwargs):
        raise technical_error

    async def _unexpected_business_route(**kwargs):
        raise AssertionError('failed exact /issue must not reach business routing')

    monkeypatch.setattr(
        'bot.handlers.runtime_issue.is_admin_telegram_user',
        _fail_admin_check,
    )
    monkeypatch.setattr(
        active_fsm_guard,
        '_resolve_navigation_for_update',
        _unexpected_business_route,
    )
    handled = asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=message,
            state=state,
            config=config,
            text=message.text,
            input_channel='text',
            telegram_update_id=552,
        )
    )

    assert handled is True
    assert message.answers == [RUNTIME_ISSUE_FAILURE]
    assert _count(config) == 0
    assert state.current == 'InvoiceStates:waiting_input'
    assert state.data == protected
    assert state.set_calls == state.clear_calls == state.update_calls == 0


@pytest.mark.parametrize(
    'technical_error',
    [
        sqlite3.OperationalError('workspace database unavailable'),
        OSError('workspace database read failed'),
    ],
)
def test_idle_workspace_read_failure_is_truthful_and_preserves_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    technical_error: Exception,
) -> None:
    config = _config(tmp_path)
    state = _State()
    message = _Message('/issue Po potvrdení sa správa nezobrazila.')

    def _fail_workspace_read(*args, **kwargs):
        raise technical_error

    monkeypatch.setattr(
        'bot.handlers.runtime_issue.WorkspaceContextService.resolve_for_user_readonly',
        _fail_workspace_read,
    )
    asyncio.run(
        cmd_runtime_issue(
            message,
            state,
            config,
            type('Update', (), {'update_id': 553})(),
        )
    )

    assert message.answers == [RUNTIME_ISSUE_FAILURE]
    assert _count(config) == 0
    assert state.current is None
    assert state.data == {}
    assert state.set_calls == state.clear_calls == state.update_calls == 0


@pytest.mark.parametrize(
    'technical_error',
    [
        sqlite3.OperationalError('workspace database unavailable'),
        OSError('workspace database read failed'),
    ],
)
def test_active_workspace_read_failure_is_handled_without_business_fallthrough(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    technical_error: Exception,
) -> None:
    config = _config(tmp_path)
    protected = {'invoice_draft': {'customer': 'Alfa'}}
    state = _State('InvoiceStates:waiting_input', protected)
    message = _Message('/issue Po potvrdení sa správa nezobrazила.')

    def _fail_workspace_read(*args, **kwargs):
        raise technical_error

    async def _unexpected_business_route(**kwargs):
        raise AssertionError('failed exact /issue must not reach business routing')

    monkeypatch.setattr(
        'bot.handlers.runtime_issue.WorkspaceContextService.resolve_for_user_readonly',
        _fail_workspace_read,
    )
    monkeypatch.setattr(
        active_fsm_guard,
        '_resolve_navigation_for_update',
        _unexpected_business_route,
    )
    handled = asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=message,
            state=state,
            config=config,
            text=message.text,
            input_channel='text',
            telegram_update_id=554,
        )
    )

    assert handled is True
    assert message.answers == [RUNTIME_ISSUE_FAILURE]
    assert _count(config) == 0
    assert state.current == 'InvoiceStates:waiting_input'
    assert state.data == protected
    assert state.set_calls == state.clear_calls == state.update_calls == 0


def test_idle_natural_text_public_route_converges_on_shared_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    seen: dict[str, object] = {}

    async def _resolver(**kwargs):
        seen.update(kwargs)
        return RUNTIME_ISSUE_ACTION

    monkeypatch.setattr(invoice, 'resolve_semantic_action', _resolver)
    message = _Message(
        'Po uložení bločku zostala stará klávesnica; ulož to ako problém.'
    )
    asyncio.run(
        invoice.semantic_top_level_input(
            message,
            _State(),
            config,
            type('Update', (), {'update_id': 601})(),
        )
    )

    assert RUNTIME_ISSUE_ACTION in seen['allowed_actions']
    assert _count(config) == 1
    assert _row(config)['source_channel'] == 'text'


@pytest.mark.parametrize(
    'text',
    [
        'Vieš nahlásiť problém?',
        'Ako nahlásim problém?',
        'Pridaj novú funkciu na export.',
        'Vystav faktúru firme Alfa na 100 eur.',
        'Pridaj kontakt Alfa s IČO 123.',
        'Zmeň adresu dodávateľa.',
        'Ulož tento bloček.',
        'Otvor dnešný pracovný deň.',
        'Nastala chyba pri účtovaní.',
        'Nejasný bežný text.',
    ],
)
def test_negative_space_and_unknown_create_no_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    text: str,
) -> None:
    config = _config(tmp_path)

    async def _unknown(**kwargs):
        return 'unknown'

    monkeypatch.setattr(invoice, 'resolve_semantic_action', _unknown)
    monkeypatch.setattr(invoice, 'resolve_info_help_triage_result_with_llm', _unknown_triage)
    asyncio.run(
        invoice.semantic_top_level_input(
            _Message(text),
            _State(),
            config,
            type('Update', (), {'update_id': 701})(),
        )
    )
    assert _count(config) == 0


async def _unknown_triage(**kwargs) -> InfoHelpTriageResult:
    return InfoHelpTriageResult()


def test_bounded_issue_resolver_contract_has_negative_space(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    async def _resolver(**kwargs):
        captured.update(kwargs)
        return RUNTIME_ISSUE_ACTION

    monkeypatch.setattr('bot.handlers.runtime_issue.resolve_semantic_action', _resolver)
    result = asyncio.run(
        resolve_runtime_issue_intent(
            text='Nahlás chybu: po potvrdení sa správa nezobrazila.',
            config=_config(tmp_path),
            current_state=None,
            input_channel='text',
        )
    )
    assert result is True
    assert captured['allowed_actions'] == [RUNTIME_ISSUE_ACTION, 'unknown']
    negative = ' '.join(
        captured['action_hints'][RUNTIME_ISSUE_ACTION]['not_this']
    )
    assert 'capability' in negative
    assert 'customization' in negative
    assert 'contact' in negative
    assert 'work-time' in negative
    assert 'merely containing' in negative


def test_non_admin_never_receives_executable_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    allowed: list[str] = []

    async def _resolver(**kwargs):
        allowed.extend(kwargs['allowed_actions'])
        return 'unknown'

    monkeypatch.setattr(invoice, 'resolve_semantic_action', _resolver)
    monkeypatch.setattr(invoice, 'resolve_info_help_triage_result_with_llm', _unknown_triage)
    asyncio.run(
        invoice.process_invoice_text(
            message=_Message(
                'Nahlás chybu: po potvrdení sa správa nezobrazila.',
                actor=USER_ID,
            ),
            state=_State(),
            config=config,
            invoice_text='Nahlás chybu: po potvrdení sa správa nezobrazila.',
            telegram_update_id=801,
        )
    )
    assert RUNTIME_ISSUE_ACTION not in allowed
    assert _count(config) == 0

    command = _Message(
        '/issue Po potvrdení sa správa nezobrazila.',
        actor=USER_ID,
        message_id=81,
    )
    asyncio.run(
        cmd_runtime_issue(
            command,
            _State(),
            config,
            type('Update', (), {'update_id': 802})(),
        )
    )
    assert command.answers == []
    assert _count(config) == 0


def test_active_fsm_capture_duplicate_bare_and_failure_preserve_protected_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    protected = {
        'invoice_draft': {'customer': 'Alfa', 'total': '100.00'},
        'active_fsm_last_activity_at': '2026-07-28T12:00:00+00:00',
    }
    state = _State('InvoiceStates:waiting_input', protected)

    async def _issue(**kwargs):
        return True

    monkeypatch.setattr(
        'bot.handlers.runtime_issue.resolve_runtime_issue_intent',
        _issue,
    )
    message = _Message('Nahlás chybu: výsledná správa sa nezobrazila.')
    handled = asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=message,
            state=state,
            config=config,
            text=message.text,
            input_channel='text',
            telegram_update_id=901,
        )
    )
    assert handled is True
    assert _count(config) == 1
    assert state.current == 'InvoiceStates:waiting_input'
    assert state.data == protected
    assert state.set_calls == state.clear_calls == state.update_calls == 0

    duplicate = _Message(message.text, message_id=31)
    asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=duplicate,
            state=state,
            config=config,
            text=duplicate.text,
            input_channel='text',
            telegram_update_id=901,
        )
    )
    assert _count(config) == 1
    assert 'už je uložený' in duplicate.answers[-1]
    assert state.data == protected

    bare = _Message('/issue', message_id=32)
    asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=bare,
            state=state,
            config=config,
            text=bare.text,
            input_channel='text',
            telegram_update_id=902,
        )
    )
    assert _count(config) == 1
    assert state.data == protected

    unsafe = _Message('/issue AAA=one\nBBB=two\nCCC=three\nspadol bot', message_id=33)
    asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=unsafe,
            state=state,
            config=config,
            text=unsafe.text,
            input_channel='text',
            telegram_update_id=903,
        )
    )
    assert _count(config) == 1
    assert 'bezpečne uložiť' in unsafe.answers[-1]
    assert state.data == protected


def test_active_admin_navigation_command_keeps_deterministic_priority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    state = _State('InvoiceStates:waiting_input', {'invoice_draft': {'x': 1}})

    async def _unexpected_issue_resolver(**kwargs):
        raise AssertionError('/cancel must not reach issue intent resolution')

    async def _cancel(**kwargs):
        await kwargs['state'].clear()
        await kwargs['message'].answer('Rozpracovaná akcia bola zrušená.')

    monkeypatch.setattr(
        'bot.handlers.runtime_issue.resolve_runtime_issue_intent',
        _unexpected_issue_resolver,
    )
    monkeypatch.setattr(active_fsm_guard, '_execute_navigation', _cancel)
    message = _Message('/cancel')
    handled = asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=message,
            state=state,
            config=config,
            text=message.text,
            input_channel='text',
            telegram_update_id=951,
        )
    )
    assert handled is True
    assert state.clear_calls == 1
    assert _count(config) == 0


def test_acknowledgement_failure_keeps_committed_issue_and_fsm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    state = _State('InvoiceStates:waiting_input', {'invoice_draft': {'x': 1}})
    message = _Message(
        '/issue Po potvrdení sa správa nezobrazila používateľovi.',
        fail_answer=True,
    )
    with pytest.raises(RuntimeError, match='telegram unavailable'):
        asyncio.run(
            active_fsm_guard.handle_active_fsm_text_update(
                message=message,
                state=state,
                config=config,
                text=message.text,
                input_channel='text',
                telegram_update_id=1001,
            )
        )
    assert _count(config) == 1
    assert state.current == 'InvoiceStates:waiting_input'
    assert state.data == {'invoice_draft': {'x': 1}}


def test_persistence_failure_is_truthful_and_preserves_active_fsm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    protected = {'invoice_draft': {'customer': 'Alfa'}}
    state = _State('InvoiceStates:waiting_input', protected)

    def _fail_capture(self, payload):
        raise RuntimeIssueError('forced persistence failure')

    monkeypatch.setattr(
        'bot.handlers.runtime_issue.RuntimeIssueService.capture',
        _fail_capture,
    )
    message = _Message(
        '/issue Po potvrdení sa správa nezobrazila používateľovi.'
    )
    handled = asyncio.run(
        active_fsm_guard.handle_active_fsm_text_update(
            message=message,
            state=state,
            config=config,
            text=message.text,
            input_channel='text',
            telegram_update_id=1051,
        )
    )
    assert handled is True
    assert message.answers == [
        'Problém sa nepodarilo uložiť. Skúste to neskôr. '
        'Aktuálna akcia bota zostala nezmenená.'
    ]
    assert _count(config) == 0
    assert state.current == 'InvoiceStates:waiting_input'
    assert state.data == protected
    assert state.clear_calls == state.set_calls == state.update_calls == 0


def test_trusted_slots_cannot_be_supplied_by_report_text(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _Message(
        '/issue actor_telegram_id=999 workspace_id=evil build_sha=deadbeef; '
        'po potvrdení sa správa nezobrazila.'
    )
    asyncio.run(
        cmd_runtime_issue(
            message,
            _State(),
            config,
            type('Update', (), {'update_id': 1101})(),
        )
    )
    row = _row(config)
    assert row['actor_telegram_id'] == ADMIN_ID
    assert row['workspace_id'] is None
    assert row['telegram_update_id'] == 1101
    assert row['telegram_message_id'] == 31
    assert row['telegram_chat_id'] == 41


def test_handler_uses_trusted_read_only_active_workspace(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            'INSERT INTO authorized_users '
            '(telegram_id, role, status, created_at, approved_by) '
            "VALUES (?, 'admin', 'active', '2026-07-28T00:00:00+00:00', ?)",
            (ADMIN_ID, ADMIN_ID),
        )
        connection.execute(
            'INSERT INTO workspace '
            '(workspace_id, display_name, storage_key, drive_folder_name, status, '
            'created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                'trusted-workspace',
                'Trusted',
                'trusted',
                'Trusted',
                'active',
                '2026-07-28T00:00:00+00:00',
                '2026-07-28T00:00:00+00:00',
            ),
        )
        connection.execute(
            'INSERT INTO workspace_membership '
            '(workspace_id, telegram_id, role, status, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (
                'trusted-workspace',
                ADMIN_ID,
                'owner',
                'active',
                '2026-07-28T00:00:00+00:00',
                '2026-07-28T00:00:00+00:00',
            ),
        )
        connection.commit()

    message = _Message(
        '/issue workspace_id=evil; po potvrdení sa správa nezobrazila.'
    )
    asyncio.run(
        cmd_runtime_issue(
            message,
            _State(),
            config,
            type('Update', (), {'update_id': 1151})(),
        )
    )
    row = _row(config)
    assert row['workspace_id'] == 'trusted-workspace'


def test_product_truth_and_info_help_are_non_executing_and_truthful(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    result = get_capability('runtime_issue_intake')
    capability = result.capability
    payload = get_safe_answer_payload('runtime_issue_intake')

    assert result.product_status == 'supported'
    assert capability.requires_admin is True
    assert capability.supported_channels == ('command', 'text', 'voice')
    assert any('opravu' in claim for claim in capability.forbidden_claims)
    assert payload['product_status'] == 'supported'

    for question in ('Vieš nahlásiť problém?', 'Ako nahlásim problém?'):
        answer = build_product_truth_guidance(user_input_text=question)
        assert answer is not None
        assert 'Nahlásenie prevádzkového problému' in answer
        assert '/issue' in answer
        assert 'nepotvrdzuje chybu' in answer
        assert _count(config) == 0


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('Error123: show invoice analytics', None),
        ('Show invoices with an error', None),
        ('-- Bug: invoice analytics chose the wrong action', 'invoice analytics chose the wrong action'),
        ('Problem', ''),
    ],
)
def test_runtime_issue_prefix_requires_a_complete_first_word(
    text: str,
    expected: str | None,
) -> None:
    assert extract_runtime_issue_prefix_description(text) == expected
