from __future__ import annotations

import argparse
import json
from pathlib import Path

from bot.services.multi_workspace_migration import MultiWorkspaceMigrationAuditor
from bot.services.multi_workspace_migration_apply import (
    MultiWorkspaceMigrationManager,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Audit, apply, or roll back the multi-workspace migration.'
    )
    parser.add_argument('--db-path', required=True, type=Path)
    parser.add_argument('--storage-root', required=True, type=Path)
    parser.add_argument(
        '--mode',
        choices=('audit', 'dry-run', 'apply', 'rollback'),
        default='audit',
    )
    parser.add_argument('--expected-fingerprint')
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--manifest-path', type=Path)
    parser.add_argument('--confirm')
    parser.add_argument(
        '--service-stopped',
        action='store_true',
        help='Explicit assertion that the bot/database writer is stopped.',
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode in {'audit', 'dry-run'}:
        auditor = MultiWorkspaceMigrationAuditor(
            db_path=args.db_path,
            storage_root=args.storage_root,
        )
        report = auditor.audit() if args.mode == 'audit' else auditor.dry_run()
    else:
        manager = MultiWorkspaceMigrationManager(
            db_path=args.db_path,
            storage_root=args.storage_root,
        )
        if args.mode == 'apply':
            if not args.expected_fingerprint or args.backup_dir is None:
                raise SystemExit(
                    'apply requires --expected-fingerprint and --backup-dir'
                )
            report = manager.apply(
                expected_fingerprint=args.expected_fingerprint,
                backup_dir=args.backup_dir,
                confirmation=args.confirm or '',
                service_stopped=args.service_stopped,
            )
        else:
            if not args.expected_fingerprint or args.manifest_path is None:
                raise SystemExit(
                    'rollback requires --expected-fingerprint and --manifest-path'
                )
            report = manager.rollback(
                manifest_path=args.manifest_path,
                expected_current_fingerprint=args.expected_fingerprint,
                confirmation=args.confirm or '',
                service_stopped=args.service_stopped,
            )
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())