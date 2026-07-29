from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import tempfile

from bot.services.runtime_issue_handoff import WORKSHOP_BRANCH


QUEUE_SCHEMA_VERSION = 'autorepair-workshop-v1'
LOG_HEADING = '# Runtime Issue Autorepair Workshop Log'


class RuntimeIssueWorkshopError(RuntimeError):
    pass


def bootstrap_workshop(directory: Path, *, now: datetime | None = None) -> dict[str, str]:
    moment = (now or datetime.now(UTC)).astimezone(UTC)
    directory.mkdir(parents=True, exist_ok=True)
    queue_path = directory / 'AUTOREPAIR_QUEUE.json'
    log_path = directory / 'AUTOREPAIR_LOG.md'
    queue = {
        'schema_version': QUEUE_SCHEMA_VERSION,
        'workshop_branch': WORKSHOP_BRANCH,
        'updated_at': moment.isoformat(),
        'source_issues': [],
        'findings': [],
    }
    log = (
        f'{LOG_HEADING}\n\n'
        'Append-oriented sanitized workshop log. Receipts, evidence, findings, '
        'repairs, and production events appear here only after they are verified.\n'
    )
    _ensure_queue(queue_path, queue)
    _ensure_log(log_path, log)
    return {'queue': str(queue_path), 'log': str(log_path)}


def _ensure_queue(path: Path, seed: dict[str, object]) -> None:
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeIssueWorkshopError('workshop_queue_incompatible') from exc
        if not isinstance(current, dict):
            raise RuntimeIssueWorkshopError('workshop_queue_incompatible')
        if (
            current.get('schema_version') != QUEUE_SCHEMA_VERSION
            or current.get('workshop_branch') != WORKSHOP_BRANCH
            or not isinstance(current.get('updated_at'), str)
            or not isinstance(current.get('source_issues'), list)
            or not isinstance(current.get('findings'), list)
        ):
            raise RuntimeIssueWorkshopError('workshop_queue_incompatible')
        return
    _atomic_write(
        path,
        json.dumps(seed, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
    )


def _ensure_log(path: Path, seed: str) -> None:
    if path.exists():
        try:
            current = path.read_text(encoding='utf-8')
        except OSError as exc:
            raise RuntimeIssueWorkshopError('workshop_log_incompatible') from exc
        if not current.startswith(LOG_HEADING) or 'sanitized workshop log' not in current:
            raise RuntimeIssueWorkshopError('workshop_log_incompatible')
        return
    _atomic_write(path, seed)


def _atomic_write(path: Path, content: str) -> None:
    descriptor, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
