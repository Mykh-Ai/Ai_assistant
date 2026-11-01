"""Read-only rollout inventory. Never initializes schema or repairs jobs."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote

from bot.services.archive_delivery import configured_route


def audit(db_path: Path) -> dict:
    uri = 'file:' + quote(str(db_path.resolve()), safe='/') + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute('PRAGMA query_only=ON')
        connection.row_factory = sqlite3.Row
        integrity = connection.execute('PRAGMA quick_check').fetchone()[0]
        tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        rows = connection.execute('SELECT job_id,workspace_id,document_type,status FROM archive_jobs ORDER BY job_id').fetchall() if 'archive_jobs' in tables else []
        contexts = {r[0] for r in connection.execute('SELECT job_id FROM archive_delivery_context')} if 'archive_delivery_context' in tables else set()
        counts = {}
        blockers = []
        for row in rows:
            counts[row['status']] = counts.get(row['status'], 0) + 1
            if row['status'] in {'pending','retry_wait','uploading'} and row['job_id'] not in contexts:
                if configured_route(row['workspace_id'],row['document_type']) is not None:
                    blockers.append({'job_ref':sha256(row['job_id'].encode()).hexdigest()[:12],
                                     'document_type':row['document_type'],'status':row['status'],
                                     'reason':'legacy_routed_job_requires_reviewed_disposition'})
        return {'integrity':integrity,'job_counts':counts,'delivery_contexts':len(contexts),
                'activation_blockers':blockers,'read_only':True,
                'schema_apply_performed':False,'live_permissions_verified':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    options = parser.parse_args()
    print(json.dumps(audit(options.db), sort_keys=True))


if __name__ == '__main__':
    main()
