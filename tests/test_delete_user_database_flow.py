from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3

import pytest

from bot.config import Config
from bot.handlers.access_admin import cmd_approve, cmd_users
from bot.handlers.delete_user_database import (
    DELETE_USER_DATABASE_SAFE_EXIT_HINT,
    DELETE_USER_DATABASE_WARNING,
    EXACT_DELETE_DATABASE_CONFIRMATION,
    VOICE_EXACT_CONFIRMATION_MESSAGE,
    DeleteUserDatabaseStates,
    cmd_vymazat_databazu,
    confirm_delete_user_database,
)
from bot.handlers.invoice import process_invoice_text
from bot.handlers.state_control import STATE_CANCELLED_MESSAGE, cancel_alias
from bot.handlers.voice import handle_voice
from bot.services.access_control import (
    ACCESS_STATUS_DELETED_DATABASE,
    ACCESS_STATUS_PENDING,
    AUTHORIZED_STATUS_ACTIVE,
    AUTHORIZED_STATUS_DELETED_DATABASE,
    AccessControlService,
)
from bot.services.api_enrollment import ApiEnrollmentError, ApiEnrollmentService
from bot.services.api_session import ApiSessionError, ApiSessionService
from bot.services.authorization import ACCESS_REQUEST_MESSAGE, TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db, managed_connection
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.principal_identity import PrincipalIdentityService
from bot.services.semantic_action_resolver import resolve_semantic_action
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.user_data_deletion import UserDataDeletionService


ADMIN_ID = 990001
USER_A = 990101
USER_B = 990202
UNKNOWN_ID = 990303


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.username = f'user{user_id}'
        self.first_name = 'Test'
        self.last_name = 'User'


class _DummyMessage:
    def __init__(self, text: str, user_id: int) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []
        self.documents: list[str] = []
        self.message_id = 1
        self.update_id = 1
        self.voice = None

    async def answer(self, text: str) -> None:
        self.answers.append(text)

    async def answer_document(self, document, caption: str | None = None) -> None:
        self.documents.append(caption or '')


class _DummyVoice:
    def __init__(self, file_id: str = 'voice-delete') -> None:
        self.file_id = file_id


class _DummyVoiceMessage(_DummyMessage):
    def __init__(self, user_id: int) -> None:
        super().__init__('', user_id)
        self.voice = _DummyVoice()


class _DummyBot:
    class _File:
        file_path = 'voice.ogg'

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def get_file(self, file_id: str):
        return self._File()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'voice')

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.sent.append((telegram_id, text))


class _DummyState:
    def __init__(self, current_state: str | None = None) -> None:
        self.current_state = current_state
        self.data: dict = {}
        self.cleared = False

    async def get_state(self) -> str | None:
        return self.current_state

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, 'state') else state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()
        self.cleared = True


class _DeleteActionOpenAIFake:
    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _ = kwargs
        return type(
            '_Response',
            (),
            {'choices': [type('_Choice', (), {'message': type('_Message', (), {'content': '{"canonical_action":"delete_user_database"}'})()})()]},
        )()


def _config(
    tmp_path: Path,
    *,
    api_key: str | None = None,
    allowed: frozenset[int] = frozenset(),
    admins: frozenset[int] = frozenset({ADMIN_ID}),
) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=api_key,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'delete-user.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=allowed,
        admin_telegram_user_ids=admins,
    )


def _supplier(user_id: int) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=user_id,
        name=f'Supplier {user_id}',
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Bratislava 1',
        iban='SK3112000000198742637541',
        swift='TATRSKBX',
        email=f'supplier-{user_id}@example.com',
        smtp_host=None,
        smtp_user=None,
        smtp_pass=None,
        days_due=14,
    )


def _contact(user_id: int, *, name: str, contract_path: str | None = None) -> ContactProfile:
    return ContactProfile(
        supplier_telegram_id=user_id,
        name=name,
        ico='87654321',
        dic='0987654321',
        ic_dph=None,
        address='Kosice 1',
        email='',
        contact_person=None,
        source_type='manual',
        source_note=None,
        contract_path=contract_path,
    )


def _item() -> CreateInvoiceItemPayload:
    return CreateInvoiceItemPayload(
        description_raw='service',
        description_normalized='Service',
        item_description_raw=None,
        quantity=1,
        unit='ks',
        unit_price=100,
        total_price=100,
    )


def _setup_authorized_user(config: Config, user_id: int) -> None:
    AccessControlService(config.db_path).approve_user(telegram_id=user_id, approved_by=ADMIN_ID)


def _setup_business_data(config: Config, user_id: int, *, contract_path: Path) -> int:
    supplier_service = SupplierService(config.db_path)
    supplier_service.create_or_replace(_supplier(user_id))
    supplier = supplier_service.get_by_telegram_id(user_id)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(config.db_path).create_mapping(supplier.id, 'oprava', 'Oprava')
    contact_service = ContactService(config.db_path)
    contact_service.create_or_replace(_contact(user_id, name=f'Customer {user_id}', contract_path=str(contract_path)))
    contact = contact_service.get_by_name(user_id, f'Customer {user_id}')
    assert contact is not None and contact.id is not None
    contact_service.create_confirmed_contact_alias(
        supplier_telegram_id=user_id,
        alias_text=f'Alias {user_id}',
        contact_id=contact.id,
        source='test',
    )
    invoice_service = InvoiceService(config.db_path)
    invoice_service.set_first_invoice_number(
        supplier_telegram_id=user_id,
        issue_year=2026,
        first_invoice_number='20260025',
    )
    return invoice_service.create_invoice_with_items(
        supplier_telegram_id=user_id,
        contact_id=contact.id,
        issue_date='2026-05-05',
        delivery_date='2026-05-05',
        due_date='2026-05-19',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='draft',
        items=[_item()],
        invoice_number='20260025',
    )


def _count(db_path: Path, sql: str, params: tuple = ()) -> int:
    with managed_connection(db_path) as connection:
        row = connection.execute(sql, params).fetchone()
    return int(row[0])


def _setup_api_credentials(config: Config, user_id: int):
    enrollments = ApiEnrollmentService(config.db_path)
    consumed = enrollments.issue_for_authorized_telegram_user(
        telegram_id=user_id,
        device_label=f'Active {user_id}',
    )
    credentials = enrollments.exchange(consumed.enrollment_secret)
    pending = enrollments.issue_for_authorized_telegram_user(
        telegram_id=user_id,
        device_label=f'Pending {user_id}',
    )
    identity = PrincipalIdentityService(config.db_path).resolve_telegram_identity(
        user_id
    )
    assert identity is not None
    return credentials, pending, identity


def _assert_api_credentials_untouched(
    config: Config,
    user_id: int,
    credentials,
    pending,
) -> None:
    assert ApiSessionService(config.db_path).authenticate_access(
        credentials.access_token
    )
    statuses = {
        item.enrollment_id: item
        for item in ApiEnrollmentService(config.db_path).list_status_for_telegram_user(
            user_id
        )
    }
    assert statuses[pending.enrollment_id].status == 'pending'
    assert statuses[pending.enrollment_id].revoked_at is None


def test_vymazat_databazu_command_starts_warning_state_without_deleting(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _setup_authorized_user(config, USER_A)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
    message = _DummyMessage('/vymazat_databazu', USER_A)
    state = _DummyState()

    asyncio.run(cmd_vymazat_databazu(message, state, config))

    assert state.current_state == DeleteUserDatabaseStates.waiting_exact_confirmation.state
    assert message.answers == [DELETE_USER_DATABASE_WARNING]
    assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is not None
    assert AccessControlService(config.db_path).get_authorized_user(USER_A).status == AUTHORIZED_STATUS_ACTIVE


def test_top_level_text_delete_database_starts_same_warning_state(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _setup_authorized_user(config, USER_A)
    message = _DummyMessage('Chcem vymazať moju databázu', USER_A)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == DeleteUserDatabaseStates.waiting_exact_confirmation.state
    assert message.answers == [DELETE_USER_DATABASE_WARNING]


def test_voice_delete_database_intent_starts_warning_state(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path, api_key='key')
    init_db(config.db_path)
    _setup_authorized_user(config, USER_A)

    async def _stt(*args, **kwargs) -> str:
        return 'хочу удалить мою базу'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    message = _DummyVoiceMessage(USER_A)
    state = _DummyState()

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert state.current_state == DeleteUserDatabaseStates.waiting_exact_confirmation.state
    assert message.answers == [DELETE_USER_DATABASE_WARNING]


def test_delete_user_database_resolver_obeys_allowed_actions(monkeypatch) -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['delete_user_database', 'unknown'],
            user_input_text='zrušiť môj účet',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_user_database'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'unknown'],
            user_input_text='zrušiť môj účet',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'

    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _DeleteActionOpenAIFake)
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['delete_user_database', 'unknown'],
            user_input_text='please remove my entire account',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'delete_user_database'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'unknown'],
            user_input_text='please remove my entire account',
            api_key='sk-test',
            model='gpt-4o',
        )
    ) == 'unknown'


def test_wrong_typed_confirmation_does_not_delete_or_revoke(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _setup_authorized_user(config, USER_A)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
    credentials, pending, _ = _setup_api_credentials(config, USER_A)
    message = _DummyMessage('vymazat databazu', USER_A)
    state = _DummyState(DeleteUserDatabaseStates.waiting_exact_confirmation.state)

    asyncio.run(confirm_delete_user_database(message, state, config))

    assert state.current_state == DeleteUserDatabaseStates.waiting_exact_confirmation.state
    assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is not None
    assert AccessControlService(config.db_path).get_authorized_user(USER_A).status == AUTHORIZED_STATUS_ACTIVE
    assert 'napíšte presne' in message.answers[-1]
    assert DELETE_USER_DATABASE_SAFE_EXIT_HINT in message.answers[-1]
    _assert_api_credentials_untouched(
        config,
        USER_A,
        credentials,
        pending,
    )


def test_delete_database_global_cancel_aliases_clear_state_without_deletion(tmp_path: Path) -> None:
    for index, alias in enumerate(('zrušiť', 'назад')):
        config = _config(tmp_path / f'alias-{index}')
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(config.db_path)
        _setup_authorized_user(config, USER_A)
        SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
        credentials, pending, _ = _setup_api_credentials(config, USER_A)
        message = _DummyMessage(alias, USER_A)
        state = _DummyState(DeleteUserDatabaseStates.waiting_exact_confirmation.state)

        asyncio.run(cancel_alias(message, state, config))

        assert state.current_state is None
        assert message.answers == [STATE_CANCELLED_MESSAGE]
        assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is not None
        assert AccessControlService(config.db_path).get_authorized_user(USER_A).status == AUTHORIZED_STATUS_ACTIVE
        _assert_api_credentials_untouched(
            config,
            USER_A,
            credentials,
            pending,
        )


def test_voice_in_final_confirmation_state_never_deletes_or_calls_stt(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path, api_key=None)
    init_db(config.db_path)
    _setup_authorized_user(config, USER_A)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
    credentials, pending, _ = _setup_api_credentials(config, USER_A)

    async def _stt(*args, **kwargs) -> str:
        raise AssertionError('STT must not run for exact delete confirmation state')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    message = _DummyVoiceMessage(USER_A)
    state = _DummyState(DeleteUserDatabaseStates.waiting_exact_confirmation.state)

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert message.answers == [VOICE_EXACT_CONFIRMATION_MESSAGE]
    assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is not None
    assert AccessControlService(config.db_path).get_authorized_user(USER_A).status == AUTHORIZED_STATUS_ACTIVE
    _assert_api_credentials_untouched(
        config,
        USER_A,
        credentials,
        pending,
    )


def test_exact_delete_terminalizes_only_target_api_credentials_and_fresh_enrollment_works(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    access = AccessControlService(config.db_path)
    _setup_authorized_user(config, USER_A)
    _setup_authorized_user(config, USER_B)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
    SupplierService(config.db_path).create_or_replace(_supplier(USER_B))
    credentials_a, pending_a, identity_a = _setup_api_credentials(config, USER_A)
    credentials_b, pending_b, identity_b = _setup_api_credentials(config, USER_B)

    message = _DummyMessage(EXACT_DELETE_DATABASE_CONFIRMATION, USER_A)
    state = _DummyState(DeleteUserDatabaseStates.waiting_exact_confirmation.state)
    asyncio.run(confirm_delete_user_database(message, state, config))

    assert state.cleared is True
    assert access.get_authorized_user(USER_A).status == AUTHORIZED_STATUS_DELETED_DATABASE
    assert PrincipalIdentityService(config.db_path).resolve_telegram_identity(USER_A) == identity_a
    assert PrincipalIdentityService(config.db_path).resolve_telegram_identity(USER_B) == identity_b
    sessions_a = ApiSessionService(config.db_path).list_sessions_for_telegram_user(USER_A)
    sessions_b = ApiSessionService(config.db_path).list_sessions_for_telegram_user(USER_B)
    assert [item.status for item in sessions_a] == ['revoked']
    assert [item.status for item in sessions_b] == ['active']
    enrollment_a = {
        item.enrollment_id: item
        for item in ApiEnrollmentService(config.db_path).list_status_for_telegram_user(USER_A)
    }
    enrollment_b = {
        item.enrollment_id: item
        for item in ApiEnrollmentService(config.db_path).list_status_for_telegram_user(USER_B)
    }
    assert enrollment_a[pending_a.enrollment_id].status == 'revoked'
    assert enrollment_a[pending_a.enrollment_id].revoked_at is not None
    assert sorted(item.status for item in enrollment_a.values()) == ['consumed', 'revoked']
    assert enrollment_b[pending_b.enrollment_id].status == 'pending'
    assert sorted(item.status for item in enrollment_b.values()) == ['consumed', 'pending']
    with pytest.raises(ApiSessionError):
        ApiSessionService(config.db_path).authenticate_access(credentials_a.access_token)
    with pytest.raises(ApiSessionError):
        ApiSessionService(config.db_path).rotate_refresh(credentials_a.refresh_token)
    with pytest.raises(ApiEnrollmentError):
        ApiEnrollmentService(config.db_path).exchange(pending_a.enrollment_secret)
    assert ApiSessionService(config.db_path).authenticate_access(credentials_b.access_token)

    access.approve_user(telegram_id=USER_A, approved_by=ADMIN_ID)
    with pytest.raises(ApiSessionError):
        ApiSessionService(config.db_path).authenticate_access(credentials_a.access_token)
    with pytest.raises(ApiSessionError):
        ApiSessionService(config.db_path).rotate_refresh(credentials_a.refresh_token)
    with pytest.raises(ApiEnrollmentError):
        ApiEnrollmentService(config.db_path).exchange(pending_a.enrollment_secret)

    fresh_issue = ApiEnrollmentService(config.db_path).issue_for_authorized_telegram_user(
        telegram_id=USER_A,
        device_label='Fresh trust',
    )
    fresh = ApiEnrollmentService(config.db_path).exchange(
        fresh_issue.enrollment_secret
    )
    assert fresh.access_token != credentials_a.access_token
    assert ApiSessionService(config.db_path).authenticate_access(fresh.access_token)
    final_sessions = ApiSessionService(config.db_path).list_sessions_for_telegram_user(
        USER_A
    )
    assert sorted(item.status for item in final_sessions) == ['active', 'revoked']


def test_delete_database_failure_rolls_back_business_access_and_api_credentials(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _setup_authorized_user(config, USER_A)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
    credentials, pending, _ = _setup_api_credentials(config, USER_A)
    filesystem_calls: list[bool] = []

    def _fail_mark_deleted(*args, **kwargs) -> None:
        raise sqlite3.OperationalError('injected reset failure')

    def _unexpected_filesystem(*args, **kwargs):
        filesystem_calls.append(True)
        return [], [], []

    monkeypatch.setattr(
        'bot.services.user_data_deletion.mark_deleted_database_in_connection',
        _fail_mark_deleted,
    )
    monkeypatch.setattr(
        UserDataDeletionService,
        '_delete_scoped_filesystem_paths',
        _unexpected_filesystem,
    )
    with pytest.raises(sqlite3.OperationalError, match='injected reset failure'):
        UserDataDeletionService(config.db_path, config.storage_dir).delete_user_database(
            telegram_id=USER_A
        )

    assert filesystem_calls == []
    assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is not None
    assert AccessControlService(config.db_path).get_authorized_user(USER_A).status == AUTHORIZED_STATUS_ACTIVE
    _assert_api_credentials_untouched(config, USER_A, credentials, pending)


def test_partial_filesystem_failure_keeps_account_and_credentials_terminal(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _setup_authorized_user(config, USER_A)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
    credentials, pending, _ = _setup_api_credentials(config, USER_A)

    monkeypatch.setattr(
        UserDataDeletionService,
        '_delete_scoped_filesystem_paths',
        lambda *args, **kwargs: ([], [], ['simulated filesystem failure']),
    )
    result = UserDataDeletionService(
        config.db_path,
        config.storage_dir,
    ).delete_user_database(telegram_id=USER_A)

    assert result.filesystem_errors == ('simulated filesystem failure',)
    assert AccessControlService(config.db_path).get_authorized_user(USER_A).status == AUTHORIZED_STATUS_DELETED_DATABASE
    with pytest.raises(ApiSessionError):
        ApiSessionService(config.db_path).authenticate_access(credentials.access_token)
    with pytest.raises(ApiEnrollmentError):
        ApiEnrollmentService(config.db_path).exchange(pending.enrollment_secret)


def test_exact_confirmation_deletes_only_current_user_data_and_marks_deleted_database(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    access = AccessControlService(config.db_path)
    _setup_authorized_user(config, USER_A)
    _setup_authorized_user(config, USER_B)

    contract_a = tmp_path / 'contracts' / 'contract-a.pdf'
    contract_b = tmp_path / 'contracts' / 'contract-b.pdf'
    unreferenced_contract = tmp_path / 'contracts' / 'unreferenced.pdf'
    for path in (contract_a, contract_b, unreferenced_contract):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'contract')
    invoice_a_id = _setup_business_data(config, USER_A, contract_path=contract_a)
    invoice_b_id = _setup_business_data(config, USER_B, contract_path=contract_b)
    assert _count(config.db_path, 'SELECT COUNT(*) FROM principal') == 0

    for path in (
        tmp_path / 'invoices' / str(USER_A) / '20260025.pdf',
        tmp_path / 'invoices' / str(USER_B) / '20260025.pdf',
        tmp_path / 'workspaces' / f'telegram-{USER_A}' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'metadata' / 'a.json',
        tmp_path / 'workspaces' / f'telegram-{USER_B}' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'metadata' / 'b.json',
        tmp_path / 'uploads' / 'accounting_intake' / str(USER_A) / 'upload' / 'original.pdf',
        tmp_path / 'uploads' / 'accounting_intake' / str(USER_B) / 'upload' / 'original.pdf',
        tmp_path / 'uploads' / 'attachment_intake' / str(USER_A) / 'upload' / 'original.pdf',
        tmp_path / 'uploads' / 'attachment_intake' / str(USER_B) / 'upload' / 'original.pdf',
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'data')

    message = _DummyMessage(EXACT_DELETE_DATABASE_CONFIRMATION, USER_A)
    state = _DummyState(DeleteUserDatabaseStates.waiting_exact_confirmation.state)

    asyncio.run(confirm_delete_user_database(message, state, config))

    assert state.current_state is None
    assert access.get_authorized_user(USER_A).status == AUTHORIZED_STATUS_DELETED_DATABASE
    assert access.get_access_request(USER_A).status == ACCESS_STATUS_DELETED_DATABASE
    assert access.get_authorized_user(USER_B).status == AUTHORIZED_STATUS_ACTIVE
    assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is None
    assert SupplierService(config.db_path).get_by_telegram_id(USER_B) is not None
    assert ContactService(config.db_path).get_all_by_supplier(USER_A) == []
    assert len(ContactService(config.db_path).get_all_by_supplier(USER_B)) == 1
    assert _count(config.db_path, 'SELECT COUNT(*) FROM invoice WHERE supplier_telegram_id = ?', (USER_A,)) == 0
    assert _count(config.db_path, 'SELECT COUNT(*) FROM invoice WHERE supplier_telegram_id = ?', (USER_B,)) == 1
    assert _count(config.db_path, 'SELECT COUNT(*) FROM invoice_item WHERE invoice_id = ?', (invoice_a_id,)) == 0
    assert _count(config.db_path, 'SELECT COUNT(*) FROM invoice_item WHERE invoice_id = ?', (invoice_b_id,)) == 1
    assert _count(config.db_path, 'SELECT COUNT(*) FROM invoice_number_settings WHERE supplier_telegram_id = ?', (USER_A,)) == 0
    assert _count(config.db_path, 'SELECT COUNT(*) FROM confirmed_semantic_alias WHERE supplier_telegram_id = ?', (USER_A,)) == 0
    assert _count(config.db_path, 'SELECT COUNT(*) FROM principal') == 0
    assert not (tmp_path / 'invoices' / str(USER_A)).exists()
    assert (tmp_path / 'invoices' / str(USER_B)).exists()
    assert not (tmp_path / 'workspaces' / f'telegram-{USER_A}').exists()
    assert (tmp_path / 'workspaces' / f'telegram-{USER_B}').exists()
    assert not (tmp_path / 'uploads' / 'accounting_intake' / str(USER_A)).exists()
    assert (tmp_path / 'uploads' / 'accounting_intake' / str(USER_B)).exists()
    assert not (tmp_path / 'uploads' / 'attachment_intake' / str(USER_A)).exists()
    assert (tmp_path / 'uploads' / 'attachment_intake' / str(USER_B)).exists()
    assert not contract_a.exists()
    assert contract_b.exists()
    assert unreferenced_contract.exists()


def test_deleted_database_user_start_requires_new_approval_and_reapproval_keeps_database_clean(tmp_path: Path) -> None:
    config = _config(tmp_path, allowed=frozenset({USER_A}))
    init_db(config.db_path)
    access = AccessControlService(config.db_path)
    _setup_authorized_user(config, USER_A)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A))
    delete_message = _DummyMessage(EXACT_DELETE_DATABASE_CONFIRMATION, USER_A)
    asyncio.run(
        confirm_delete_user_database(
            delete_message,
            _DummyState(DeleteUserDatabaseStates.waiting_exact_confirmation.state),
            config,
        )
    )
    assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is None

    supplier_message = _DummyMessage('/supplier', USER_A)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler')

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, supplier_message, {'config': config}))
    assert calls == []
    assert supplier_message.answers == [UNAUTHORIZED_MESSAGE]

    start_message = _DummyMessage('/start', USER_A)
    bot = _DummyBot()
    asyncio.run(
        TelegramUserAuthorizationMiddleware()(
            _handler,
            start_message,
            {'config': config, 'state': _DummyState(), 'bot': bot},
        )
    )
    assert access.get_access_request(USER_A).status == ACCESS_STATUS_PENDING
    assert start_message.answers == [ACCESS_REQUEST_MESSAGE]

    users_message = _DummyMessage('/users', ADMIN_ID)
    asyncio.run(cmd_users(users_message, config))
    assert f'telegram_id={USER_A}' in users_message.answers[-1]
    assert 'status=deleted_database' in users_message.answers[-1]

    approve_message = _DummyMessage(f'/approve {USER_A}', ADMIN_ID)
    approval_bot = _DummyBot()
    asyncio.run(cmd_approve(approve_message, config, bot=approval_bot))
    assert access.get_authorized_user(USER_A).status == AUTHORIZED_STATUS_ACTIVE
    assert approval_bot.sent and approval_bot.sent[0][0] == USER_A
    assert 'FakturaBot' in approval_bot.sent[0][1]
    assert SupplierService(config.db_path).get_by_telegram_id(USER_A) is None
