from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3
import sys

from bot.services.api_enrollment import ApiEnrollmentError, ApiEnrollmentService
from bot.services.api_session import ApiSessionError, ApiSessionService
from bot.services.db import init_db
from bot.services.principal_identity import PrincipalIdentityError


class _BoundedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        self.print_usage(sys.stderr)
        self.exit(2, f'{self.prog}: error: invalid_arguments\n')


def _parser() -> argparse.ArgumentParser:
    parser = _BoundedArgumentParser(prog='officeflow_api_access')
    subparsers = parser.add_subparsers(dest='command', required=True)

    issue = subparsers.add_parser('issue')
    issue.add_argument('--telegram-id', type=int, required=True)
    issue.add_argument('--expires-in-seconds', type=int, default=1800)
    issue.add_argument('--device-label')

    revoke = subparsers.add_parser('revoke-enrollment')
    revoke.add_argument('--enrollment-id', required=True)

    status = subparsers.add_parser('status')
    status.add_argument('--telegram-id', type=int, required=True)

    sessions = subparsers.add_parser('sessions')
    sessions.add_argument('--telegram-id', type=int, required=True)

    revoke_session = subparsers.add_parser('revoke-session')
    revoke_session.add_argument('--telegram-id', type=int, required=True)
    revoke_session.add_argument('--session-id', required=True)
    return parser


def _db_path() -> Path:
    return Path(os.getenv('DB_PATH', 'storage/fakturabot.db')).resolve()


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if getattr(args, 'telegram_id', 1) <= 0:
            raise ApiEnrollmentError('telegram_identity_invalid')
        db_path = _db_path()
        init_db(db_path)
        service = ApiEnrollmentService(db_path)
        sessions = ApiSessionService(db_path)
        if args.command == 'issue':
            issued = service.issue_for_authorized_telegram_user(
                telegram_id=args.telegram_id,
                ttl=timedelta(seconds=args.expires_in_seconds),
                device_label=args.device_label,
            )
            result: object = {
                'enrollment_id': issued.enrollment_id,
                'enrollment_secret': issued.enrollment_secret,
                'expires_at': issued.expires_at,
                'device_label': issued.device_label,
                'warning': 'Enrollment secret is displayed once and cannot be recovered.',
            }
        elif args.command == 'revoke-enrollment':
            service.revoke_outstanding(args.enrollment_id)
            result = {
                'enrollment_id': args.enrollment_id,
                'status': 'revoked',
            }
        elif args.command == 'status':
            result = {
                'enrollments': [
                    asdict(item)
                    for item in service.list_status_for_telegram_user(
                        args.telegram_id
                    )
                ]
            }
        elif args.command == 'sessions':
            result = {
                'sessions': [
                    asdict(item)
                    for item in sessions.list_sessions_for_telegram_user(
                        args.telegram_id
                    )
                ]
            }
        else:
            result = asdict(
                sessions.revoke_session_for_telegram_user(
                    telegram_id=args.telegram_id,
                    session_id=args.session_id,
                )
            )
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                separators=(',', ':'),
                sort_keys=True,
            )
        )
        return 0
    except sqlite3.Error:
        print(
            json.dumps(
                {'error': 'officeflow_api_access_storage_failed', 'status': 'failed'},
                separators=(',', ':'),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    except (
        ApiEnrollmentError,
        ApiSessionError,
        PrincipalIdentityError,
        RuntimeError,
        OSError,
    ) as exc:
        code = str(exc)
        if len(code) > 128 or any(c in code for c in '\r\n\x00'):
            code = 'officeflow_api_access_failed'
        print(
            json.dumps(
                {'error': code, 'status': 'failed'},
                separators=(',', ':'),
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
