from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

from bot.services.runtime_issue_handoff import (
    RuntimeIssueHandoffError,
    RuntimeIssueHandoffService,
)


_TOKEN = re.compile(r'^[A-Za-z0-9_-]{43,128}$')
_TOKEN_INPUT_MAX = 128


class _BoundedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        self.print_usage(sys.stderr)
        self.exit(2, f'{self.prog}: error: invalid_arguments\n')


def _parser() -> argparse.ArgumentParser:
    parser = _BoundedArgumentParser(prog='runtime_issue_handoff')
    subparsers = parser.add_subparsers(dest='command', required=True)
    take = subparsers.add_parser('take-next')
    take.add_argument('--limit', type=int, required=True)
    take.add_argument('--format', choices=('json',), required=True)
    claim = subparsers.add_parser('claim')
    claim.add_argument('--handoff-id', required=True)
    claim.add_argument('--lease-token-stdin', action='store_true', required=True)
    claim.add_argument('--manifest-digest', required=True)
    return parser


def _db_path() -> Path:
    return Path(os.getenv('DB_PATH', 'storage/fakturabot.db')).resolve()


def _stdin_token() -> str:
    raw = sys.stdin.read(_TOKEN_INPUT_MAX + 2)
    if not raw or len(raw) > _TOKEN_INPUT_MAX or '\n' in raw or '\r' in raw:
        raise RuntimeIssueHandoffError('lease_token_stdin_invalid')
    if not _TOKEN.fullmatch(raw):
        raise RuntimeIssueHandoffError('lease_token_stdin_invalid')
    return raw


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        service = RuntimeIssueHandoffService(_db_path())
        if args.command == 'take-next':
            handoffs = service.take_next(limit=args.limit)
            result: object = {
                'schema_version': 'runtime-issue-handoff-batch-v1',
                'handoffs': handoffs,
            }
        else:
            token = _stdin_token()
            claim = service.claim(
                handoff_id=args.handoff_id,
                raw_token=token,
                manifest_digest=args.manifest_digest,
            )
            result = {
                'schema_version': 'runtime-issue-handoff-claim-v2',
                'handoff_id': claim.handoff_id,
                'status': claim.status,
                'delivery_state': 'accepted_by_agent',
                'manifest_digest': claim.manifest_digest,
                'acknowledged_at': claim.acknowledged_at,
                'idempotent': claim.idempotent,
            }
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':'), sort_keys=True))
        return 0
    except (RuntimeIssueHandoffError, RuntimeError, OSError) as exc:
        print(
            json.dumps(
                {'error': str(exc), 'status': 'failed'},
                separators=(',', ':'),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
