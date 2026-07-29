from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from bot.services.runtime_issue_evidence import (
    FixedDockerLogSource,
    RuntimeIssueEvidenceError,
    RuntimeIssueEvidenceService,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='runtime_issue_evidence')
    subparsers = parser.add_subparsers(dest='command', required=True)
    collect = subparsers.add_parser('collect')
    collect.add_argument('--issue-id', required=True)
    collect.add_argument('--handoff-id', required=True)
    collect.add_argument('--format', choices=('json',), required=True)
    try:
        args = parser.parse_args(argv)
        service = RuntimeIssueEvidenceService(
            Path(os.getenv('DB_PATH', 'storage/fakturabot.db')).resolve(),
            source=FixedDockerLogSource(),
        )
        result = service.collect(issue_id=args.issue_id, handoff_id=args.handoff_id)
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':'), sort_keys=True))
        return 0
    except (RuntimeIssueEvidenceError, RuntimeError, OSError) as exc:
        print(
            json.dumps({'error': str(exc), 'status': 'failed'}, sort_keys=True),
            file=sys.stderr,
        )
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
