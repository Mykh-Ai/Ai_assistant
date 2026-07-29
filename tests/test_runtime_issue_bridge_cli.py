from __future__ import annotations

import json
import sys

import pytest

from bot.cli import runtime_issue_handoff
from bot.services.runtime_issue_handoff import AckResult


def test_ack_parser_has_no_argv_token_value_option(capsys):
    token = 'never-argv-sensitive-value'
    actions = {
        option
        for action in runtime_issue_handoff._parser()._actions
        for option in action.option_strings
    }
    assert '--lease-token' not in actions
    with pytest.raises(SystemExit):
        runtime_issue_handoff._parser().parse_args(
            ['ack', '--lease-token', token]
        )
    captured = capsys.readouterr()
    assert token not in captured.out
    assert token not in captured.err


@pytest.mark.parametrize(
    'value',
    ['', 'A' * 42, 'A' * 129, 'A' * 43 + '\n', 'A' * 43 + '\ntrailing'],
)
def test_stdin_token_is_strict_and_error_never_exposes_value(monkeypatch, value):
    monkeypatch.setattr(sys, 'stdin', type('Input', (), {'read': lambda self, size: value})())
    with pytest.raises(Exception) as error:
        runtime_issue_handoff._stdin_token()
    if value:
        assert value not in str(error.value)


def test_ack_output_never_contains_raw_token(monkeypatch, capsys):
    token = 'A' * 43

    class FakeService:
        def __init__(self, path):
            del path

        def acknowledge(self, **kwargs):
            assert kwargs.pop('raw_token') == token
            kwargs.pop('verifier')
            return AckResult(
                handoff_id=kwargs['handoff_id'],
                status='acknowledged',
                manifest_digest=kwargs['manifest_digest'],
                workshop_branch=kwargs['workshop_branch'],
                workshop_commit_sha=kwargs['workshop_commit_sha'],
                acknowledged_at='2026-07-29T08:00:00+00:00',
                idempotent=False,
            )

    monkeypatch.setattr(runtime_issue_handoff, 'RuntimeIssueHandoffService', FakeService)
    monkeypatch.setattr(sys, 'stdin', type('Input', (), {'read': lambda self, size: token})())
    exit_code = runtime_issue_handoff.main(
        [
            'ack',
            '--handoff-id',
            'RH-20260729-ABCDEF123456',
            '--lease-token-stdin',
            '--manifest-digest',
            'sha256:' + 'a' * 64,
            '--workshop-branch',
            'maintenance/runtime-issue-workshop',
            '--workshop-commit',
            'b' * 40,
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert token not in captured.out
    assert token not in captured.err
    assert json.loads(captured.out)['status'] == 'acknowledged'


def test_take_next_stdout_is_only_json(monkeypatch, capsys):
    class FakeService:
        def __init__(self, path):
            del path

        def take_next(self, *, limit):
            assert limit == 3
            return []

    monkeypatch.setattr(runtime_issue_handoff, 'RuntimeIssueHandoffService', FakeService)
    assert runtime_issue_handoff.main(
        ['take-next', '--limit', '3', '--format', 'json']
    ) == 0
    captured = capsys.readouterr()
    assert captured.err == ''
    assert json.loads(captured.out) == {
        'schema_version': 'runtime-issue-handoff-batch-v1',
        'handoffs': [],
    }
