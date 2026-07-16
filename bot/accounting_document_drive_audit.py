from __future__ import annotations

import argparse
import json
from pathlib import Path

from bot.services.accounting_document_drive_audit import (
    audit_accounting_document_drive_targets,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Read-only audit of active accounting-document Drive targets.',
    )
    parser.add_argument('--db-path', type=Path, required=True)
    args = parser.parse_args()

    report = audit_accounting_document_drive_targets(args.db_path)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.deployment_ready else 2


if __name__ == '__main__':
    raise SystemExit(main())
