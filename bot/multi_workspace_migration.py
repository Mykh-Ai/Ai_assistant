from __future__ import annotations

import argparse
import json
from pathlib import Path

from bot.services.multi_workspace_migration import MultiWorkspaceMigrationAuditor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Audit the multi-workspace migration source shape.'
    )
    parser.add_argument('--db-path', required=True, type=Path)
    parser.add_argument('--storage-root', required=True, type=Path)
    parser.add_argument('--mode', choices=('audit', 'dry-run'), default='audit')
    return parser


def main() -> int:
    args = build_parser().parse_args()
    auditor = MultiWorkspaceMigrationAuditor(
        db_path=args.db_path,
        storage_root=args.storage_root,
    )
    report = auditor.audit() if args.mode == 'audit' else auditor.dry_run()
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())