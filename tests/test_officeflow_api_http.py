from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3

from aiohttp.test_utils import TestClient, TestServer
import pytest

from bot.officeflow_api_app import create_officeflow_api_app
from bot.services.access_control import AccessControlService
from bot.services.api_enrollment import ApiEnrollmentService
from bot.services.contact_service import ContactProfile
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_invoice_pdf_storage import WorkspaceInvoicePdfStorageService
from bot.services.workspace_invoice_service import WorkspaceInvoiceService
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


USER_A = 760_001
USER_B = 760_002
ADMIN = 760_999


@dataclass(frozen=True)
class Seed:
    db_path: Path
    storage_dir: Path
    token: str
    workspace_a: object
    invoice_a: object
    contact_a: ContactProfile
    workspace_b: object
    invoice_b: object


def _supplier(user_id: int, name: str) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=user_id,
        name=name,
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address=f'{name} address',
        iban='SK3112000000198742637541',
        swift='GIBASKBX',
        email=f'{name.lower().replace(" ", "-")}@example.test',
        smtp_host=None,
        smtp_user=None,
        smtp_pass=None,
        days_due=14,
    )


def _contact(user_id: int, workspace_id: str, name: str) -> ContactProfile:
    return ContactProfile(
        workspace_id=workspace_id,
        supplier_telegram_id=user_id,
        name=name,
        ico='87654321',
        dic='0987654321',
        ic_dph=None,
        address=f'{name} address',
        email=f'{name.lower().replace(" ", "-")}@example.test',
        iban='SK6811000000002941482306',
        contact_person='Office Manager',
        source_type='manual',
        source_note='private source note',
        contract_path='/private/contracts/customer.pdf',
    )


def _item() -> CreateInvoiceItemPayload:
    return CreateInvoiceItemPayload(
        description_raw='Consulting',
        description_normalized='Consulting',
        item_description_raw='August services',
        quantity=2,
        unit='hour',
        unit_price=50,
        total_price=100,
    )


def _create_workspace(
    db_path: Path,
    *,
    user_id: int,
    workspace_id: str,
    name: str,
):
    return WorkspaceProfileService(db_path).create_profile(
        actor_telegram_id=user_id,
        profile=_supplier(user_id, name),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
        workspace_id=workspace_id,
        storage_key=workspace_id,
    )


def _seed(tmp_path: Path) -> Seed:
    db_path = tmp_path / 'officeflow.db'
    storage_dir = tmp_path / 'storage'
    init_db(db_path)
    access = AccessControlService(db_path)
    for user_id in (USER_A, USER_B):
        access.approve_user(telegram_id=user_id, approved_by=ADMIN, role='owner')

    workspace_a = _create_workspace(
        db_path,
        user_id=USER_A,
        workspace_id='ws_a',
        name='Workspace A',
    )
    workspace_b = _create_workspace(
        db_path,
        user_id=USER_B,
        workspace_id='ws_b',
        name='Workspace B',
    )
    contacts = WorkspaceContactService(db_path)
    contact_a = contacts.create_or_replace(
        workspace_a,
        _contact(USER_A, workspace_a.workspace_id, 'Customer A'),
    )
    contact_b = contacts.create_or_replace(
        workspace_b,
        _contact(USER_B, workspace_b.workspace_id, 'Customer B'),
    )
    invoices = WorkspaceInvoiceService(db_path)
    invoice_a = invoices.create_invoice_with_items(
        workspace_a,
        contact_id=int(contact_a.id),
        issue_date='2026-08-01',
        delivery_date='2026-08-01',
        due_date='2026-08-15',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='created',
        items=[_item()],
        invoice_number='20260001',
    )
    invoice_b = invoices.create_invoice_with_items(
        workspace_b,
        contact_id=int(contact_b.id),
        issue_date='2026-08-02',
        delivery_date='2026-08-02',
        due_date='2026-08-16',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='created',
        items=[_item()],
        invoice_number='20260001',
    )
    pdf_path = storage_dir / 'invoices' / workspace_a.storage_key / '20260001.pdf'
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b'%PDF-1.4\nowned officeflow invoice\n%%EOF\n')
    WorkspaceInvoicePdfStorageService(db_path, storage_dir).persist_path(
        workspace_a,
        invoice_id=invoice_a.id,
        pdf_path=pdf_path,
    )
    enrollment = ApiEnrollmentService(db_path)
    issued = enrollment.issue_for_authorized_telegram_user(
        telegram_id=USER_A,
        device_label='Android pilot',
    )
    credentials = enrollment.exchange(issued.enrollment_secret)
    return Seed(
        db_path=db_path,
        storage_dir=storage_dir,
        token=credentials.access_token,
        workspace_a=workspace_a,
        invoice_a=invoice_a,
        contact_a=contact_a,
        workspace_b=workspace_b,
        invoice_b=invoice_b,
    )


async def _request_async(
    seed: Seed,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: object | None = None,
) -> tuple[int, dict[str, object] | bytes, dict[str, str]]:
    app = create_officeflow_api_app(
        db_path=seed.db_path,
        storage_dir=seed.storage_dir,
    )
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        headers = {'Authorization': f'Bearer {token or seed.token}'}
        response = await client.request(method, path, headers=headers, json=json_body)
        response_headers = dict(response.headers)
        if response.content_type == 'application/json':
            body: dict[str, object] | bytes = await response.json()
        else:
            body = await response.read()
        return response.status, body, response_headers
    finally:
        await client.close()


def _request(
    seed: Seed,
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: object | None = None,
) -> tuple[int, dict[str, object] | bytes, dict[str, str]]:
    return asyncio.run(
        _request_async(
            seed,
            method,
            path,
            token=token,
            json_body=json_body,
        )
    )


def test_http_temporary_block_is_nonterminal_but_deleted_access_is_terminal(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    enrollment = ApiEnrollmentService(seed.db_path)
    issued = enrollment.issue_for_authorized_telegram_user(
        telegram_id=USER_A,
        device_label='Block semantics',
    )
    credentials = enrollment.exchange(issued.enrollment_secret)
    access = AccessControlService(seed.db_path)

    access.block_user(telegram_id=USER_A, decided_by=ADMIN)
    status, body, _ = _request(
        seed,
        'GET',
        '/v1/session',
        token=credentials.access_token,
    )
    assert status == 423
    assert body == {'error': {'code': 'access_temporarily_unavailable'}}
    status, body, _ = _request(
        seed,
        'POST',
        '/v1/session/refresh',
        json_body={'refresh_token': credentials.refresh_token},
    )
    assert status == 423
    assert body == {'error': {'code': 'access_temporarily_unavailable'}}

    access.approve_user(telegram_id=USER_A, approved_by=ADMIN, role='owner')
    status, _, _ = _request(
        seed,
        'GET',
        '/v1/session',
        token=credentials.access_token,
    )
    assert status == 200

    access.mark_deleted_database(telegram_id=USER_A)
    status, body, _ = _request(
        seed,
        'GET',
        '/v1/session',
        token=credentials.access_token,
    )
    assert status == 401
    assert body == {'error': {'code': 'unauthorized'}}


def test_http_enrollment_exchange_refresh_rotation_and_replay(tmp_path: Path) -> None:
    seed = _seed(tmp_path)
    enrollment = ApiEnrollmentService(seed.db_path).issue_for_authorized_telegram_user(
        telegram_id=USER_A,
        device_label='Second device',
    )

    status, body, headers = _request(
        seed,
        'POST',
        '/v1/enrollment/exchange',
        json_body={'enrollment_secret': enrollment.enrollment_secret},
    )
    assert status == 200
    assert headers['Cache-Control'] == 'no-store'
    session = body['session']
    assert session['access_token'].startswith('ofacc_')
    assert session['refresh_token'].startswith('ofref_')
    response_text = json.dumps(body)
    assert 'principal_id' not in response_text
    assert 'session_id' not in response_text
    assert 'hash' not in response_text

    replay = _request(
        seed,
        'POST',
        '/v1/enrollment/exchange',
        json_body={'enrollment_secret': enrollment.enrollment_secret},
    )[:2]
    assert replay == (401, {'error': {'code': 'invalid_enrollment'}})

    old_refresh = session['refresh_token']
    status, refreshed, _ = _request(
        seed,
        'POST',
        '/v1/session/refresh',
        json_body={'refresh_token': old_refresh},
    )
    assert status == 200
    assert refreshed['session']['refresh_token'] != old_refresh
    old_replay = _request(
        seed,
        'POST',
        '/v1/session/refresh',
        json_body={'refresh_token': old_refresh},
    )[:2]
    assert old_replay == (401, {'error': {'code': 'unauthorized'}})


def test_auth_credentials_and_hashes_are_not_logged(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    seed = _seed(tmp_path)
    enrollment = ApiEnrollmentService(seed.db_path).issue_for_authorized_telegram_user(
        telegram_id=USER_A
    )
    caplog.set_level('DEBUG')

    status, body, _ = _request(
        seed,
        'POST',
        '/v1/enrollment/exchange',
        json_body={'enrollment_secret': enrollment.enrollment_secret},
    )

    assert status == 200
    response_text = json.dumps(body)
    with sqlite3.connect(seed.db_path) as connection:
        stored_hashes = connection.execute(
            'SELECT access_token_hash, refresh_token_hash FROM api_session'
        ).fetchall()
    assert enrollment.enrollment_secret not in caplog.text
    assert body['session']['access_token'] not in caplog.text
    assert body['session']['refresh_token'] not in caplog.text
    assert all(value not in response_text for row in stored_hashes for value in row)


def test_http_auth_payloads_are_strict_and_bounded(tmp_path: Path) -> None:
    seed = _seed(tmp_path)
    status, body, _ = _request(
        seed,
        'POST',
        '/v1/enrollment/exchange',
        json_body={'enrollment_secret': 'ofenr_' + ('x' * 43), 'principal_id': 'forged'},
    )
    assert status == 400
    assert body == {'error': {'code': 'invalid_request'}}

    status, body, _ = _request(seed, 'GET', '/v1/invoices?telegram_id=760001')
    assert status == 400
    assert body == {'error': {'code': 'invalid_request'}}

    status, body, _ = _request(
        seed,
        'POST',
        '/v1/enrollment/exchange',
        json_body={'enrollment_secret': 'x' * (17 * 1024)},
    )
    assert status == 413
    assert body == {'error': {'code': 'request_too_large'}}


def _business_snapshot(db_path: Path) -> dict[str, list[tuple[object, ...]]]:
    with sqlite3.connect(db_path) as connection:
        return {
            table: connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
            for table in (
                'supplier',
                'contact',
                'invoice',
                'invoice_item',
                'active_workspace_selection',
            )
        }


def test_session_and_workspace_list_are_current_authorized_and_sanitized(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)

    status, session_body, headers = _request(seed, 'GET', '/v1/session')
    assert status == 200
    assert headers['Cache-Control'] == 'no-store'
    text = json.dumps(session_body)
    assert 'principal' not in text
    assert 'session_id' not in text
    assert 'token_hash' not in text
    assert seed.token not in text

    status, body, _ = _request(seed, 'GET', '/v1/workspaces')
    assert status == 200
    assert body == {
        'workspaces': [
            {'workspace_id': 'ws_a', 'display_name': 'Workspace A', 'role': 'owner'}
        ]
    }

    AccessControlService(seed.db_path).block_user(
        telegram_id=USER_A,
        decided_by=ADMIN,
    )
    status, body, _ = _request(seed, 'GET', '/v1/workspaces')
    assert status == 423
    assert body == {'error': {'code': 'access_temporarily_unavailable'}}


def test_single_workspace_default_reads_without_selection_mutation(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    before = _business_snapshot(seed.db_path)

    status, body, _ = _request(seed, 'GET', '/v1/invoices')
    assert status == 200
    assert body['workspace_id'] == 'ws_a'
    assert [row['id'] for row in body['invoices']] == [seed.invoice_a.id]

    status, body, _ = _request(seed, 'GET', '/v1/contacts')
    assert status == 200
    assert [row['id'] for row in body['contacts']] == [seed.contact_a.id]
    assert _business_snapshot(seed.db_path) == before


def test_api_read_has_no_telegram_fsm_dependency_or_mutation(tmp_path: Path) -> None:
    seed = _seed(tmp_path)
    telegram_fsm = {
        'state': 'InvoiceStates:waiting_confirmation',
        'data': {'draft_id': 'telegram-draft', 'workspace_id': 'ws_a'},
        'revision': 7,
    }
    before = json.loads(json.dumps(telegram_fsm))

    status, _, _ = _request(seed, 'GET', '/v1/invoices?workspace_id=ws_a')

    assert status == 200
    assert telegram_fsm == before


def test_multi_workspace_requires_explicit_scope_and_ignores_active_selection(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    second = WorkspaceProfileService(seed.db_path).create_profile(
        actor_telegram_id=USER_A,
        profile=_supplier(USER_A, 'Workspace A2'),
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
        make_active=False,
        workspace_id='ws_a2',
        storage_key='ws_a2',
    )
    before = _business_snapshot(seed.db_path)

    status, body, _ = _request(seed, 'GET', '/v1/invoices')
    assert status == 409
    assert body == {'error': {'code': 'workspace_selection_required'}}

    status, body, _ = _request(
        seed,
        'GET',
        f'/v1/invoices?workspace_id={second.workspace_id}',
    )
    assert status == 200
    assert body['workspace_id'] == second.workspace_id
    assert body['invoices'] == []
    assert _business_snapshot(seed.db_path) == before


def test_invoice_detail_foreign_and_nonexistent_are_indistinguishable_and_sanitized(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    owned_path = f'/v1/invoices/{seed.invoice_a.id}?workspace_id=ws_a'
    status, body, _ = _request(seed, 'GET', owned_path)
    assert status == 200
    text = json.dumps(body)
    assert body['invoice']['id'] == seed.invoice_a.id
    for forbidden in (
        'supplier_telegram_id',
        'telegram_id',
        'pdf_path',
        'contract_path',
        str(seed.storage_dir),
    ):
        assert forbidden not in text

    foreign = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_b.id}?workspace_id=ws_a',
    )[:2]
    missing = _request(
        seed,
        'GET',
        '/v1/invoices/9223372036854775807?workspace_id=ws_a',
    )[:2]
    assert foreign == missing == (404, {'error': {'code': 'not_found'}})

    status, body, _ = _request(seed, 'GET', '/v1/invoices?workspace_id=ws_b')
    assert status == 404
    assert body == {'error': {'code': 'workspace_not_found'}}


def test_contacts_are_allowlisted_and_foreign_workspace_fails_closed(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    status, body, _ = _request(seed, 'GET', '/v1/contacts?workspace_id=ws_a')
    assert status == 200
    text = json.dumps(body)
    assert body['contacts'][0]['name'] == 'Customer A'
    for forbidden in (
        'supplier_telegram_id',
        'telegram_id',
        'contract_path',
        'source_note',
        '/private/',
    ):
        assert forbidden not in text

    status, _, _ = _request(seed, 'GET', '/v1/contacts?workspace_id=ws_b')
    assert status == 404


def test_owned_pdf_streams_but_missing_unsafe_and_foreign_fail_without_generation(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    before_files = sorted(path.relative_to(seed.storage_dir) for path in seed.storage_dir.rglob('*'))
    status, body, headers = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )
    assert status == 200
    assert isinstance(body, bytes) and body.startswith(b'%PDF-')
    assert headers['Content-Type'] == 'application/pdf'
    assert int(headers['Content-Length']) == len(body)
    assert str(seed.storage_dir) not in json.dumps(dict(headers))

    foreign = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_b.id}/pdf?workspace_id=ws_a',
    )[:2]
    assert foreign == (404, {'error': {'code': 'not_found'}})

    with sqlite3.connect(seed.db_path) as connection:
        connection.execute(
            'UPDATE invoice SET pdf_path = ? WHERE id = ?',
            (str(tmp_path / 'outside.pdf'), seed.invoice_a.id),
        )
        connection.commit()
    (tmp_path / 'outside.pdf').write_bytes(b'%PDF-1.4\nunsafe')
    status, body, _ = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )
    assert status == 404
    assert str(tmp_path) not in json.dumps(body)
    after_files = sorted(path.relative_to(seed.storage_dir) for path in seed.storage_dir.rglob('*'))
    assert after_files == before_files


def test_missing_pdf_fails_boundedly_without_regeneration(tmp_path: Path) -> None:
    seed = _seed(tmp_path)
    with sqlite3.connect(seed.db_path) as connection:
        pointer = connection.execute(
            'SELECT pdf_path FROM invoice WHERE id = ?',
            (seed.invoice_a.id,),
        ).fetchone()[0]
    Path(pointer).unlink()
    before = sorted(path.relative_to(seed.storage_dir) for path in seed.storage_dir.rglob('*'))

    status, body, _ = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )

    assert status == 404
    assert body == {'error': {'code': 'not_found'}}
    after = sorted(path.relative_to(seed.storage_dir) for path in seed.storage_dir.rglob('*'))
    assert after == before


def test_poisoned_pdf_pointer_to_foreign_workspace_fails_closed(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    foreign_pdf = (
        seed.storage_dir
        / 'invoices'
        / seed.workspace_b.storage_key
        / f'{seed.invoice_a.invoice_number}.pdf'
    )
    foreign_pdf.parent.mkdir(parents=True, exist_ok=True)
    foreign_pdf.write_bytes(b'%PDF-1.4\nforeign workspace secret\n%%EOF\n')
    with sqlite3.connect(seed.db_path) as connection:
        connection.execute(
            'UPDATE invoice SET pdf_path = ? WHERE id = ?',
            (str(foreign_pdf), seed.invoice_a.id),
        )
        connection.commit()

    status, body, headers = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )

    assert status == 404
    assert body == {'error': {'code': 'not_found'}}
    assert b'foreign workspace secret' not in json.dumps(body).encode()
    assert str(foreign_pdf) not in json.dumps(body)
    assert str(foreign_pdf) not in json.dumps(headers)


def test_legacy_pdf_root_requires_unambiguous_invoice_file_ownership(
    tmp_path: Path,
) -> None:
    seed = _seed(tmp_path)
    legacy_actor_pdf = (
        seed.storage_dir
        / 'invoices'
        / str(USER_A)
        / f'{seed.invoice_a.invoice_number}.pdf'
    )
    legacy_actor_pdf.parent.mkdir(parents=True, exist_ok=True)
    legacy_actor_pdf.write_bytes(b'%PDF-1.4\nunambiguous legacy owner\n%%EOF\n')
    flat_legacy_pdf = (
        seed.storage_dir
        / 'invoices'
        / f'{seed.invoice_a.invoice_number}.pdf'
    )
    flat_legacy_pdf.write_bytes(b'%PDF-1.4\nambiguous flat legacy\n%%EOF\n')
    with sqlite3.connect(seed.db_path) as connection:
        connection.execute(
            'UPDATE invoice SET pdf_path = ? WHERE id = ?',
            (str(legacy_actor_pdf), seed.invoice_a.id),
        )
        connection.commit()

    status, body, _ = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )
    assert status == 200
    assert body.startswith(b'%PDF-1.4\nunambiguous legacy owner')

    with sqlite3.connect(seed.db_path) as connection:
        connection.execute(
            'UPDATE invoice SET pdf_path = ? WHERE id = ?',
            (str(flat_legacy_pdf), seed.invoice_a.id),
        )
        connection.commit()
    status, body, _ = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )
    assert status == 404
    assert body == {'error': {'code': 'not_found'}}

    workspace_a2 = WorkspaceProfileService(seed.db_path).create_profile(
        actor_telegram_id=USER_A,
        profile=_supplier(USER_A, 'Workspace A2'),
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
        make_active=False,
        workspace_id='ws_a2',
        storage_key='ws_a2',
    )
    with sqlite3.connect(seed.db_path) as connection:
        connection.execute(
            'UPDATE invoice SET pdf_path = ? WHERE id = ?',
            (str(legacy_actor_pdf), seed.invoice_a.id),
        )
        connection.commit()
    status, body, _ = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )
    assert status == 200
    assert body.startswith(b'%PDF-1.4\nunambiguous legacy owner')

    contact_a2 = WorkspaceContactService(seed.db_path).create_or_replace(
        workspace_a2,
        _contact(USER_A, workspace_a2.workspace_id, 'Customer A2'),
    )
    WorkspaceInvoiceService(seed.db_path).create_invoice_with_items(
        workspace_a2,
        contact_id=int(contact_a2.id),
        issue_date='2026-08-03',
        delivery_date='2026-08-03',
        due_date='2026-08-17',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='created',
        items=[_item()],
        invoice_number=seed.invoice_a.invoice_number,
    )
    status, body, _ = _request(
        seed,
        'GET',
        f'/v1/invoices/{seed.invoice_a.id}/pdf?workspace_id=ws_a',
    )
    assert status == 404
    assert body == {'error': {'code': 'not_found'}}


@pytest.mark.parametrize(
    ('method', 'path'),
    [
        ('POST', '/v1/invoices'),
        ('DELETE', '/v1/invoices/1'),
        ('POST', '/v1/invoices/1/mark-paid'),
        ('POST', '/v1/workspaces/switch'),
        ('POST', '/v1/action'),
    ],
)
def test_guessed_mutation_routes_have_zero_business_effects(
    tmp_path: Path,
    method: str,
    path: str,
) -> None:
    seed = _seed(tmp_path)
    before = _business_snapshot(seed.db_path)

    status, body, _ = _request(seed, method, path, json_body={})

    assert status in {404, 405}
    assert body in (
        {'error': {'code': 'not_found'}},
        {'error': {'code': 'method_not_allowed'}},
    )
    assert _business_snapshot(seed.db_path) == before


def test_session_delete_revokes_only_api_access(tmp_path: Path) -> None:
    seed = _seed(tmp_path)
    before = _business_snapshot(seed.db_path)

    status, body, _ = _request(seed, 'DELETE', '/v1/session')
    assert status == 204
    assert body == b''
    status, _, _ = _request(seed, 'GET', '/v1/session')
    assert status == 401
    assert _business_snapshot(seed.db_path) == before
