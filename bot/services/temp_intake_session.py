from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import shutil
from typing import Any

from aiogram.types import ReplyKeyboardRemove


INTAKE_TIMEOUT_SECONDS = 5 * 60
ORPHAN_CLEANUP_MAX_AGE_SECONDS = 24 * 60 * 60
TIMEOUT_MESSAGE_SK = (
    'Spracovanie bolo ukončené z dôvodu nečinnosti. '
    'Pošlite doklad znova, keď budete pripravený.'
)

_STARTED_AT_KEY = 'intake_started_at'
_EXPIRES_AT_KEY = 'intake_expires_at'
_TEMP_PATHS_KEY = 'intake_temp_paths'
_CLEANUP_KIND_KEY = 'intake_cleanup_kind'


class TempIntakeSessionError(ValueError):
    pass


def build_intake_session_metadata(
    *,
    temp_paths: list[Path | str],
    cleanup_kind: str,
    now: datetime | None = None,
    timeout_seconds: int = INTAKE_TIMEOUT_SECONDS,
) -> dict[str, object]:
    started_at = _utc_now(now)
    expires_at = started_at + timedelta(seconds=timeout_seconds)
    return {
        _STARTED_AT_KEY: _format_timestamp(started_at),
        _EXPIRES_AT_KEY: _format_timestamp(expires_at),
        _TEMP_PATHS_KEY: [str(path) for path in temp_paths],
        _CLEANUP_KIND_KEY: cleanup_kind,
    }


def is_intake_session_expired(data: dict[str, Any], now: datetime | None = None) -> bool:
    expires_at = _parse_timestamp(data.get(_EXPIRES_AT_KEY))
    if expires_at is None:
        return False
    return _utc_now(now) >= expires_at


def cleanup_expired_intake_session(*, storage_dir: Path, data: dict[str, Any]) -> None:
    cleanup_intake_temp_paths(storage_dir=storage_dir, temp_paths=_extract_temp_paths(data))


async def ensure_intake_session_active(*, message, state, storage_dir: Path, now: datetime | None = None) -> bool:
    data = await state.get_data()
    if not is_intake_session_expired(data, now=now):
        return True

    cleanup_expired_intake_session(storage_dir=storage_dir, data=data)
    await state.clear()
    await message.answer(TIMEOUT_MESSAGE_SK, reply_markup=ReplyKeyboardRemove(remove_keyboard=True))
    return False


def cleanup_intake_temp_paths(*, storage_dir: Path, temp_paths: list[Path | str]) -> None:
    for raw_path in temp_paths:
        path = Path(raw_path)
        _assert_allowed_temp_path(storage_dir=storage_dir, path=path)
        if path.is_file():
            path.unlink()
        parent = path.parent
        if parent.exists() and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()


def cleanup_old_intake_temp_dirs(
    *,
    storage_dir: Path,
    now: datetime | None = None,
    max_age_seconds: int = ORPHAN_CLEANUP_MAX_AGE_SECONDS,
) -> list[Path]:
    cutoff = _utc_now(now) - timedelta(seconds=max_age_seconds)
    removed: list[Path] = []
    for root in _allowed_temp_roots(storage_dir):
        if not root.exists():
            continue
        for child in root.iterdir():
            if not child.is_dir():
                continue
            _assert_allowed_temp_path(storage_dir=storage_dir, path=child)
            modified_at = datetime.fromtimestamp(child.stat().st_mtime, tz=UTC)
            if modified_at > cutoff:
                continue
            shutil.rmtree(child)
            removed.append(child)
    return removed


def _extract_temp_paths(data: dict[str, Any]) -> list[Path | str]:
    raw_paths = data.get(_TEMP_PATHS_KEY)
    if isinstance(raw_paths, list):
        return [path for path in raw_paths if isinstance(path, (str, Path))]

    legacy_paths: list[Path | str] = []
    for key in ('officeflow_attachment_staged_path', 'accounting_document_temp_original_path'):
        value = data.get(key)
        if isinstance(value, str):
            legacy_paths.append(value)
    return legacy_paths


def _assert_allowed_temp_path(*, storage_dir: Path, path: Path) -> None:
    resolved_path = path.resolve()
    allowed_roots = [root.resolve() for root in _allowed_temp_roots(storage_dir)]
    if any(resolved_path == root or root in resolved_path.parents for root in allowed_roots):
        return
    raise TempIntakeSessionError('refusing_to_cleanup_non_intake_temp_path')


def _allowed_temp_roots(storage_dir: Path) -> list[Path]:
    uploads = storage_dir / 'uploads'
    return [
        uploads / 'attachment_intake',
        uploads / 'accounting_intake',
    ]


def _utc_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return _utc_now(parsed)
