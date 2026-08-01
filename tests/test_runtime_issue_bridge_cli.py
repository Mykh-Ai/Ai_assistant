from __future__ import annotations

import json
import sys

import pytest

from bot.cli import runtime_issue_handoff
from bot.services.runtime_issue_handoff import ClaimResult


def test_parser_exposes_claim_and_rejects_obsolete_ack():
    parser = runtime_issue_handoff._parser()
    assert parser.parse_args([
        'claim', '--handoff-id', 'RH-20260729-ABCDEF123456',
        '--lease-token-stdin', '--manifest-digest', 'sha256:' + 'a' * 64,
    ]).command == 'claim'
    with pytest.raises(SystemExit):
        parser.parse_args(['ack'])


def test_claim_parser_has_no_argv_token_value_option(capsys):
    token = 'never-argv-sensitive-value'
    actions = {
        option
        for action in runtime_issue_handoff._parser()._actions
        for option in action.option_strings
    }
    assert '--lease-token' not in actions
    with pytest.raises(SystemExit):
        runtime_issue_handoff._parser().parse_args(
            ['claim', '--lease-token', token]
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


def test_claim_output_never_contains_raw_token_or_github_fields(monkeypatch, capsys):
    token = 'A' * 43

    class FakeService:
        def __init__(self, path):
            del path

        def claim(self, **kwargs):
            assert kwargs.pop('raw_token') == token
            return ClaimResult(
                handoff_id=kwargs['handoff_id'],
                status='acknowledged',
                manifest_digest=kwargs['manifest_digest'],
                acknowledged_at='2026-07-29T08:00:00+00:00',
                idempotent=False,
            )

    monkeypatch.setattr(runtime_issue_handoff, 'RuntimeIssueHandoffService', FakeService)
    monkeypatch.setattr(sys, 'stdin', type('Input', (), {'read': lambda self, size: token})())
    exit_code = runtime_issue_handoff.main(
        [
            'claim',
            '--handoff-id',
            'RH-20260729-ABCDEF123456',
            '--lease-token-stdin',
            '--manifest-digest',
            'sha256:' + 'a' * 64,
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert token not in captured.out
    assert token not in captured.err
    payload = json.loads(captured.out)
    assert payload['status'] == 'acknowledged'
    assert payload['delivery_state'] == 'accepted_by_agent'
    assert 'workshop_branch' not in payload
    assert 'workshop_commit_sha' not in payload


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
