from __future__ import annotations

import importlib
import inspect
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from bot.officeflow_api_app import (
    create_officeflow_api_app,
    load_officeflow_api_config,
)
from bot.services.access_control import AccessControlService
from bot.services.contact_service import ContactProfile
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload
from bot.services.product_truth import ProductTruthStatus, get_capability, list_capabilities
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_invoice_service import WorkspaceInvoiceService
from bot.services.workspace_profile_service import (
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


USER_ID = 770_001
NEW_TABLES = {
    'principal',
    'principal_external_identity',
    'api_enrollment',
    'api_session',
}
NEW_INDEXES = {
    'idx_principal_external_identity_principal_status',
    'idx_api_enrollment_principal_status_expires',
    'idx_api_session_principal_status',
}


def _seed_business_rows(db_path: Path, pdf_path: str):
    AccessControlService(db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=999,
        role='owner',
    )
    workspace = WorkspaceProfileService(db_path).create_profile(
        actor_telegram_id=USER_ID,
        profile=SupplierProfile(
            telegram_id=USER_ID,
            name='Legacy Business',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Legacy address',
            iban='SK3112000000198742637541',
            swift='GIBASKBX',
            email='legacy@example.test',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        ),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
        workspace_id='ws_legacy',
        storage_key='legacy',
    )
    contact = WorkspaceContactService(db_path).create_or_replace(
        workspace,
        ContactProfile(
            workspace_id=workspace.workspace_id,
            supplier_telegram_id=USER_ID,
            name='Legacy Customer',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='Customer address',
            email='customer@example.test',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        ),
    )
    invoice = WorkspaceInvoiceService(db_path).create_invoice_with_items(
        workspace,
        contact_id=int(contact.id),
        issue_date='2026-01-02',
        delivery_date='2026-01-02',
        due_date='2026-01-16',
        due_days=14,
        total_amount=25,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='Legacy service',
                description_normalized='Legacy service',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=25,
                total_price=25,
            )
        ],
        invoice_number='20260001',
    )
    WorkspaceInvoiceService(db_path).save_pdf_path(
        workspace,
        invoice_id=invoice.id,
        pdf_path=pdf_path,
    )
    return workspace, contact, invoice


def _rows(connection: sqlite3.Connection, table: str) -> list[tuple[object, ...]]:
    return connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()


def test_additive_bootstrap_preserves_existing_business_database(tmp_path: Path) -> None:
    db_path = tmp_path / 'legacy.db'
    init_db(db_path)
    # Normalize the established bootstrap's second-pass invoice index behavior
    # before modeling a database that predates only the Stage A tables.
    init_db(db_path)
    workspace, contact, invoice = _seed_business_rows(
        db_path,
        '/srv/fakturabot/storage/invoices/legacy/20260001.pdf',
    )
    business_tables = (
        'authorized_users',
        'workspace',
        'workspace_membership',
        'active_workspace_selection',
        'supplier',
        'contact',
        'invoice',
        'invoice_item',
    )
    with sqlite3.connect(db_path) as connection:
        for table in ('api_session', 'api_enrollment', 'principal_external_identity', 'principal'):
            connection.execute(f'DROP TABLE {table}')
        connection.commit()
        before_rows = {table: _rows(connection, table) for table in business_tables}
        before_objects = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master "
                "WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%'"
            )
        }

    init_db(db_path)

    with sqlite3.connect(db_path) as connection:
        after_rows = {table: _rows(connection, table) for table in business_tables}
        after_objects = {
            (str(row[0]), str(row[1]))
            for row in connection.execute(
                "SELECT type, name FROM sqlite_master "
                "WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert connection.execute(
            'SELECT workspace_id, contact_id, pdf_path FROM invoice WHERE id = ?',
            (invoice.id,),
        ).fetchone() == (
            workspace.workspace_id,
            contact.id,
            '/srv/fakturabot/storage/invoices/legacy/20260001.pdf',
        )
    assert after_rows == before_rows
    assert after_objects - before_objects == {
        *(('table', name) for name in NEW_TABLES),
        *(('index', name) for name in NEW_INDEXES),
    }


def test_incompatible_stage_a_table_fails_closed_without_rebuild(tmp_path: Path) -> None:
    db_path = tmp_path / 'bad.db'
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute('DROP TABLE api_session')
        connection.execute('CREATE TABLE api_session (session_id TEXT PRIMARY KEY)')
        connection.commit()

    with pytest.raises(RuntimeError, match='Incompatible local schema for table api_session'):
        init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        assert [row[1] for row in connection.execute('PRAGMA table_info(api_session)')] == [
            'session_id'
        ]


def test_api_config_has_no_telegram_token_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('BOT_TOKEN', raising=False)
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'api.db'))
    monkeypatch.setenv('STORAGE_DIR', str(tmp_path / 'storage'))

    config = load_officeflow_api_config()

    assert config.db_path == (tmp_path / 'api.db').resolve()
    assert config.storage_dir == (tmp_path / 'storage').resolve()


def test_api_import_boundary_excludes_telegram_fsm_ai_and_external_services() -> None:
    module_names = (
        'bot.officeflow_api_app',
        'bot.services.officeflow_api_context',
        'bot.services.officeflow_read_service',
        'bot.services.api_enrollment',
        'bot.services.api_session',
    )
    forbidden = (
        'aiogram',
        'bot.handlers',
        'bot.main',
        'ActiveFsm',
        'FSMContext',
        'openai',
        'SemanticActionResolver',
        'InfoHelp',
        'speech_to_text',
        'googleapiclient',
        'gmail',
    )
    for module_name in module_names:
        source = inspect.getsource(importlib.import_module(module_name))
        assert not [token for token in forbidden if token in source]

    main_source = inspect.getsource(importlib.import_module('bot.main'))
    assert 'officeflow_api_app' not in main_source


def test_fresh_api_import_does_not_load_telegram_or_ai_modules() -> None:
    code = (
        'import sys; import bot.officeflow_api_app; '
        "bad=[name for name in sys.modules if name.startswith(('aiogram','bot.handlers','openai'))]; "
        'print(bad); raise SystemExit(bool(bad))'
    )
    result = subprocess.run(
        [sys.executable, '-c', code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        env={**os.environ, 'BOT_TOKEN': ''},
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_app_factory_exposes_only_approved_stage_a_routes(tmp_path: Path) -> None:
    db_path = tmp_path / 'routes.db'
    init_db(db_path)
    app = create_officeflow_api_app(db_path=db_path, storage_dir=tmp_path)

    assert {(route.method, route.resource.canonical) for route in app.router.routes()} == {
        ('POST', '/v1/enrollment/exchange'),
        ('POST', '/v1/session/refresh'),
        ('DELETE', '/v1/session'),
        ('GET', '/v1/session'),
        ('GET', '/v1/workspaces'),
        ('GET', '/v1/invoices'),
        ('GET', '/v1/invoices/{invoice_id}'),
        ('GET', '/v1/invoices/{invoice_id}/pdf'),
        ('GET', '/v1/contacts'),
    }


def test_stage_b_registers_only_truthful_partial_android_capability() -> None:
    capability_ids = {capability.capability_id for capability in list_capabilities()}

    assert {capability_id for capability_id in capability_ids if 'android' in capability_id} == {
        'first_party_android_client'
    }
    capability = get_capability('first_party_android_client')
    assert capability.product_status == ProductTruthStatus.PARTIAL
    assert capability.capability.requires_admin is True
    assert capability.capability.requires_setup is True
    assert any(
        'controlled HTTPS pilot endpoint is active' in limitation
        for limitation in capability.capability.current_limitations
    )
    assert any(
        'real-device acceptance' in limitation
        for limitation in capability.capability.current_limitations
    )
