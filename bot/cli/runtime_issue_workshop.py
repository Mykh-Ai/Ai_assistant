from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from bot.services.runtime_issue_workshop import (
    RuntimeIssueWorkshopError,
    bootstrap_workshop,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='runtime_issue_workshop')
    subparsers = parser.add_subparsers(dest='command', required=True)
    bootstrap = subparsers.add_parser('bootstrap')
    bootstrap.add_argument(
        '--format',
        choices=('json',),
        required=True,
    )
    try:
        args = parser.parse_args(argv)
        del args
        directory = (
            Path(__file__).resolve().parents[2]
            / 'docs'
            / 'features'
            / 'runtime_issue_autorepair_v1'
            / 'workshop'
        )
        result = bootstrap_workshop(directory)
        print(json.dumps(result, separators=(',', ':'), sort_keys=True))
        return 0
    except (RuntimeIssueWorkshopError, RuntimeError, OSError) as exc:
        print(json.dumps({'error': str(exc), 'status': 'failed'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
