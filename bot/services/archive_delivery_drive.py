"""Scoped Drive I/O for persisted delivery contexts; no credential ownership."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import json
from typing import Any, Callable

from bot.services.archive_delivery import ArchiveDeliveryError, ArchiveDeliveryStore
from bot.services.db import GOOGLE_DRIVE_FOLDER_CACHE_SCHEMA, managed_connection

FOLDER_MIME = 'application/vnd.google-apps.folder'
_FIELDS = 'id,name,mimeType,parents,trashed,size,md5Checksum,appProperties,capabilities(canAddChildren)'


def _status(exc) -> int | None:
    return getattr(getattr(exc, 'resp', None), 'status', None)


def _retryable(exc) -> bool:
    status = _status(exc)
    if status != 403:
        return status is None or status in {408, 409, 429} or status >= 500
    try:
        raw = getattr(exc, 'content', b'')
        if len(raw) > 65536:
            return False
        body = json.loads(raw)
        reasons = {item.get('reason') for item in body.get('error', {}).get('errors', []) if isinstance(item, dict)}
        return bool(reasons & {'rateLimitExceeded', 'userRateLimitExceeded', 'sharingRateLimitExceeded',
                               'dailyLimitExceeded', 'backendError', 'internalError'})
    except (ValueError, TypeError, AttributeError):
        return False


def _get(service, identifier: str) -> dict | None:
    try:
        return service.files().get(fileId=identifier, fields=_FIELDS).execute()
    except Exception as exc:
        if _status(exc) == 404:
            return None
        raise


def _quote(value: str) -> str:
    return value.replace('\\', '\\\\').replace("'", "\\'")


def _folder_valid(value: dict | None, identifier: str, *, name: str | None = None, parent: str | None = None):
    if not value or value.get('id') != identifier or value.get('mimeType') != FOLDER_MIME or value.get('trashed') is not False:
        raise ArchiveDeliveryError('archive_folder_mismatch')
    if name is not None and (value.get('name') != name or value.get('parents') != [parent]):
        raise ArchiveDeliveryError('archive_folder_mismatch')
    if value.get('capabilities', {}).get('canAddChildren') is not True:
        raise ArchiveDeliveryError('archive_folder_forbidden')


def _matching_folders(service, parent: str, name: str) -> list[str]:
    result, page, seen = [], None, set()
    for _ in range(100):
        kwargs = dict(q=f"'{_quote(parent)}' in parents and name = '{_quote(name)}' and mimeType = '{FOLDER_MIME}' and trashed = false",
                      spaces='drive', fields='files(id),nextPageToken', pageSize=100)
        if page:
            kwargs['pageToken'] = page
        response = service.files().list(**kwargs).execute()
        for value in response.get('files', []):
            identifier = value.get('id')
            if not isinstance(identifier, str) or not identifier:
                raise ArchiveDeliveryError('archive_folder_mismatch')
            if identifier not in result:
                result.append(identifier)
        if len(result) > 1:
            raise ArchiveDeliveryError('archive_folder_ambiguous')
        page = response.get('nextPageToken')
        if not page:
            return result
        if page in seen:
            break
        seen.add(page)
    raise ArchiveDeliveryError('archive_folder_listing_incomplete')


def _generate_id(service) -> str:
    result = service.files().generateIds(count=1, space='drive').execute().get('ids', [])
    if len(result) != 1 or not isinstance(result[0], str) or not result[0]:
        raise ArchiveDeliveryError('archive_id_unavailable', permanent=False)
    return result[0]


def _cached_id(store, context, path: str) -> str | None:
    with managed_connection(store.db_path) as connection:
        connection.execute(GOOGLE_DRIVE_FOLDER_CACHE_SCHEMA)
        row = connection.execute('SELECT folder_id FROM google_drive_folder_cache WHERE workspace_id=? AND provider=? AND folder_path=?',
                                 (context['workspace_id'], 'google_drive', path)).fetchone()
        return str(row[0]) if row else None


def _reserve_folder(store, context, path: str, proposed: str, parent: str) -> str:
    with managed_connection(store.db_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        timestamp = datetime.now(UTC).isoformat()
        connection.execute('INSERT OR IGNORE INTO google_drive_folder_cache (workspace_id,provider,folder_path,folder_id,parent_folder_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                           (context['workspace_id'], 'google_drive', path, proposed, parent, timestamp, timestamp))
        row = connection.execute('SELECT folder_id,parent_folder_id FROM google_drive_folder_cache WHERE workspace_id=? AND provider=? AND folder_path=?',
                                 (context['workspace_id'], 'google_drive', path)).fetchone()
        if row is None or row[1] != parent:
            raise ArchiveDeliveryError('archive_folder_mismatch')
        connection.commit()
        return str(row[0])


def _folder(service, store, context, *, parent: str, name: str, key: str) -> str:
    matches = _matching_folders(service, parent, name)
    identifier = _cached_id(store, context, key)
    if identifier is None:
        identifier = _reserve_folder(store, context, key, matches[0] if matches else _generate_id(service), parent)
    if matches and matches != [identifier]:
        raise ArchiveDeliveryError('archive_folder_mismatch')
    record = _get(service, identifier)
    if record is None:
        try:
            service.files().create(body={'id': identifier, 'name': name, 'mimeType': FOLDER_MIME, 'parents': [parent]}, fields='id').execute()
        except Exception as exc:
            if _status(exc) != 409:
                raise
        record = _get(service, identifier)
        # Detect a competing/manual create; never choose first of duplicates.
        if _matching_folders(service, parent, name) != [identifier]:
            raise ArchiveDeliveryError('archive_folder_ambiguous')
    if record is None:
        raise ArchiveDeliveryError('archive_upload_unconfirmed', permanent=False)
    _folder_valid(record, identifier, name=name, parent=parent)
    return identifier


def _target(service, store, context) -> str:
    parent = context['company_root_folder_id']
    _folder_valid(_get(service, parent), parent)
    names = [context['annual_folder_template'].replace('{YYYY}', f"{context['archive_year']:04d}"),
             context['document_folder_name']]
    if context['relative_suffix']:
        names.append(context['relative_suffix'])
    key = 'document-route-v1:' + context['route_revision'] + ':' + parent
    for name in names:
        key += '/' + name
        parent = _folder(service, store, context, parent=parent, name=name, key=key)
    return store.set_once(context['job_id'], resolved_target_folder_id=parent)['resolved_target_folder_id']


def _verify_file(record: dict | None, context, identifier: str, parent: str) -> None:
    if record is None:
        raise ArchiveDeliveryError('archive_upload_unconfirmed', permanent=False)
    if record.get('id') != identifier or record.get('parents') != [parent] or record.get('trashed') is not False:
        raise ArchiveDeliveryError('archive_remote_mismatch')
    if (record.get('name') != context['output_filename'] or record.get('mimeType') != context['payload_mime_type']
        or str(record.get('size')) != str(context['payload_size']) or record.get('md5Checksum') != context['payload_md5']
        or record.get('appProperties', {}).get('archive_delivery_ref') != context['job_id']):
        raise ArchiveDeliveryError('archive_remote_mismatch')


def upload_routed_file(*, service, store: ArchiveDeliveryStore, context: dict[str, Any],
                       local_file_path: Path, media_factory: Callable) -> tuple[str, str]:
    try:
        parent = _target(service, store, context)
        context = store.get(context['job_id'])
        identifier = context['reserved_drive_file_id']
        if not identifier:
            identifier = store.reserve_file(context['job_id'], _generate_id(service))
        existing = _get(service, identifier)
        if existing is None:
            body = dict(id=identifier, name=context['output_filename'], parents=[parent],
                        mimeType=context['payload_mime_type'], appProperties={'archive_delivery_ref': context['job_id']})
            try:
                service.files().create(body=body, media_body=media_factory(local_file_path), fields='id').execute()
            except Exception as exc:
                if _status(exc) != 409:
                    # A timed-out create may already have succeeded. Reconcile its
                    # persisted ID immediately before consuming another attempt.
                    if _retryable(exc):
                        try:
                            reconciled = _get(service, identifier)
                        except Exception:
                            reconciled = None
                        if reconciled is not None:
                            _verify_file(reconciled, context, identifier, parent)
                            return identifier, parent
                    raise
            existing = _get(service, identifier)
        _verify_file(existing, context, identifier, parent)
        return identifier, parent
    except ArchiveDeliveryError:
        raise
    except Exception as exc:
        status = _status(exc)
        raise ArchiveDeliveryError('archive_upload_unconfirmed' if _retryable(exc) else 'archive_folder_forbidden',
                                   permanent=not _retryable(exc)) from None
