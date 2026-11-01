"""Real aiogram update dispatch and middleware, fake external boundaries only."""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
import json
import importlib
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from aiogram import Bot, Dispatcher, Router
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetFile, SendMessage
from aiogram.types import Chat, File, Message, PhotoSize, Update, User, Voice

from bot.config import Config
from bot.handlers import routers
from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates
from bot.services.active_fsm_guard import ActiveFsmMessageMiddleware
from bot.services.authorization import TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.db import init_db
from bot.services.archive_worker import ArchiveWorker
from bot.services.google_drive_owner_oauth_client import GoogleDriveOwnerOAuthArchiveProvider, GoogleDriveOwnerOAuthClientConfig
from bot.services.officeflow_attachment_models import OfficeFlowAttachmentClassification
from tests.test_accounting_document_intake_flow import _receipt_candidate, _fake_classify
from tests.test_archive_delivery_v1 import ACTOR, WS, FakeDrive
from tests import test_archive_delivery_v1 as delivery_fixtures


class LocalSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent = []
        self.downloads = 0
        self.active_keyboard = None

    async def close(self):
        pass

    async def make_request(self, bot, method, timeout=None):
        if isinstance(method, SendMessage):
            self.sent.append(method)
            if getattr(method.reply_markup,'remove_keyboard',False):
                self.active_keyboard=None
            elif hasattr(method.reply_markup,'keyboard'):
                self.active_keyboard=method.reply_markup
            return Message(message_id=len(self.sent),date=datetime.now(UTC),chat=Chat(id=int(method.chat_id),type='private'),text=method.text)
        if isinstance(method, GetFile):
            return File(file_id=method.file_id,file_unique_id='synthetic-file',file_path='synthetic/photo')
        raise AssertionError('Unexpected external method: '+type(method).__name__)

    async def stream_content(self, url, **kwargs):
        self.downloads += 1
        yield b'synthetic-document-bytes'


@pytest.fixture
def public_runtime(monkeypatch,request):
    fixture = delivery_fixtures.DeliveryTests(methodName='runTest')
    fixture.setUp()
    request.addfinalizer(fixture.doCleanups)
    init_db(fixture.database)
    (fixture.storage/'uploads').mkdir(parents=True,exist_ok=True)
    monkeypatch.setenv('GOOGLE_DRIVE_FAILURE_NOTICE_CUTOFF','2020-01-01T00:00:00+00:00')
    async def extract(**kwargs):
        return replace(_receipt_candidate(),issue_date='2026-09-15')
    async def classification(**kwargs):
        return OfficeFlowAttachmentClassification(document_type='receipt',confidence='high',reason='synthetic receipt')
    async def bounded(**kwargs):
        text=kwargs['user_input_text'].casefold()
        if 'áno' in text or text=='ano':return 'ano'
        if 'nie' == text:return 'nie'
        return 'unknown'
    async def semantic(**kwargs):
        return 'pass_through' if 'pass_through' in kwargs.get('allowed_actions',[]) else 'unknown'
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document',_fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata',extract)
    monkeypatch.setattr(importlib.import_module('bot.handlers.officeflow_attachment_router'),'classify_officeflow_attachment',classification)
    monkeypatch.setattr('bot.services.decision_resolver.resolve_bounded_confirmation_reply',bounded)
    monkeypatch.setattr('bot.services.decision_resolver.resolve_semantic_action',semantic)
    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_semantic_action',semantic)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action',semantic)
    fixture.config=Config(bot_token='123456:synthetic-token',openai_api_key='synthetic-key',openai_stt_model='whisper-1',openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,db_path=fixture.database,storage_dir=fixture.storage,allowed_telegram_user_ids=frozenset({ACTOR}),google_drive_enabled=True)
    yield fixture


def dispatcher():
    dp=Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(TelegramUserAuthorizationMiddleware())
    dp.message.outer_middleware(ActiveFsmMessageMiddleware())
    dp.callback_query.outer_middleware(TelegramUserAuthorizationMiddleware())
    # Isolate parent ownership without changing a registration/filter/callback.
    # These are the exact production HandlerObjects, in production router order.
    for index,actual in enumerate(routers):
        assert not actual.message._handler.filters
        clone=Router(name='synthetic-public-'+str(index))
        clone.message.handlers.extend(actual.message.handlers)
        clone.callback_query.handlers.extend(actual.callback_query.handlers)
        dp.include_router(clone)
    return dp


def update(sequence, *, text=None, photo=False, voice=False, actor=ACTOR):
    kwargs=dict(message_id=sequence,date=datetime.now(UTC),chat=Chat(id=actor,type='private'),from_user=User(id=actor,is_bot=False,first_name='Synthetic'))
    if text is not None:kwargs['text']=text
    if photo:kwargs['photo']=[PhotoSize(file_id='synthetic-photo',file_unique_id='SYNTHETIC-PHOTO',width=100,height=100)]
    if voice:kwargs['voice']=Voice(file_id='synthetic-voice',file_unique_id='SYNTHETIC-VOICE',duration=1)
    return Update(update_id=sequence,message=Message(**kwargs))


def counts(runtime):
    with sqlite3.connect(runtime.database) as c:
        return tuple(c.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('archive_jobs','archive_delivery_context'))


@pytest.mark.acceptance
@pytest.mark.parametrize('mode',['text','reply_button','voice','idle_attachment'])
def test_public_confirmed_receipt_to_verified_yearly_archive(public_runtime,monkeypatch,mode):
    runtime=public_runtime
    async def transcribe(*args,**kwargs):return 'uložiť s kategóriou'
    monkeypatch.setattr('bot.handlers.voice.transcribe_audio',transcribe)
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        sequence=1
        if mode!='idle_attachment':
            await dp.feed_update(bot,update(sequence,text='/add_blocek'),config=runtime.config);sequence+=1
            assert await state.get_state()==AccountingDocumentIntakeStates.waiting_upload.state
        await dp.feed_update(bot,update(sequence,photo=True),config=runtime.config);sequence+=1
        if mode=='idle_attachment':
            assert counts(runtime)==(0,0)
            await dp.feed_update(bot,update(sequence,text='áno'),config=runtime.config);sequence+=1
        assert await state.get_state()==AccountingDocumentIntakeStates.waiting_preview_decision.state
        assert counts(runtime)==(0,0)
        decision=update(sequence,voice=True) if mode=='voice' else update(sequence,text='✅ Uložiť s kategóriou' if mode=='reply_button' else 'uložiť s kategóriou')
        await dp.feed_update(bot,decision,config=runtime.config)
        assert await state.get_state() is None
        assert counts(runtime)==(1,1)
        assert session.sent[-1].reply_markup.remove_keyboard is True
        assert 'uložený lokálne' in session.sent[-1].text
        assert 'prebieha na pozadí' in session.sent[-1].text
        fake=FakeDrive()
        provider=GoogleDriveOwnerOAuthArchiveProvider(GoogleDriveOwnerOAuthClientConfig(
            db_path=runtime.database,crypto_provider=object(),owner_workspace_id='synthetic-google-owner',
            client_id='synthetic-client',client_secret='synthetic-secret',root_folder_id='synthetic-legacy-root'),
            drive_service=fake,media_file_upload_factory=lambda path,**kwargs:path)
        outcome=ArchiveWorker(runtime.database,provider,storage_dir=runtime.storage).process_one()
        assert outcome.status=='uploaded'
        context=runtime.store.get(outcome.job_id)
        assert context['archive_year']==2026 and context['archive_month']==9
        target=fake.records[context['resolved_target_folder_id']]
        assert target['name']=='2026-09'
        type_folder=fake.records[target['parents'][0]]
        assert type_folder['name']=='blocky'
        assert fake.records[type_folder['parents'][0]]['name']=='Zevs_2026'
        assert len([x for x in fake.creates if 'appProperties' in x])==1
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


@pytest.mark.acceptance
@pytest.mark.parametrize('decision',['neviem','❌ Zrušiť','/cancel'])
def test_public_unknown_cancel_has_no_archive_side_effect(public_runtime,decision):
    runtime=public_runtime
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        await dp.feed_update(bot,update(1,text='/add_blocek'),config=runtime.config)
        await dp.feed_update(bot,update(2,photo=True),config=runtime.config)
        assert await state.get_state()==AccountingDocumentIntakeStates.waiting_preview_decision.state
        await dp.feed_update(bot,update(3,text=decision),config=runtime.config)
        assert counts(runtime)==(0,0)
        if decision=='neviem':
            assert await state.get_state()==AccountingDocumentIntakeStates.waiting_preview_decision.state
            assert session.active_keyboard.keyboard
            assert not getattr(session.sent[-1].reply_markup,'remove_keyboard',False)
        else:
            assert await state.get_state() is None
            assert session.sent[-1].reply_markup.remove_keyboard is True
        assert not list((runtime.storage/'workspaces').rglob('receipts/originals/*'))
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


@pytest.mark.acceptance
@pytest.mark.parametrize('mode',['text','photo','voice'])
def test_public_unauthorized_blocked_before_external_or_storage(public_runtime,monkeypatch,mode):
    runtime=public_runtime
    async def forbidden(*args,**kwargs):raise AssertionError('unauthorized AI/STT call')
    monkeypatch.setattr('bot.handlers.voice.transcribe_audio',forbidden)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document',forbidden)
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        before=set(runtime.storage.rglob('*'))
        message=update(1,text='/add_blocek',actor=900002) if mode=='text' else update(1,photo=mode=='photo',voice=mode=='voice',actor=900002)
        await dp.feed_update(bot,message,config=runtime.config)
        assert counts(runtime)==(0,0)
        assert set(runtime.storage.rglob('*'))==before
        assert session.downloads==0
        assert session.sent[-1].text==UNAUTHORIZED_MESSAGE
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


@pytest.mark.acceptance
@pytest.mark.parametrize('mode',['text','voice'])
def test_public_capability_question_is_read_only(public_runtime,monkeypatch,mode):
    runtime=public_runtime
    question='Vieš zbierať bankové výpisy z Gmailu bez hesla?'
    async def transcribe(*args,**kwargs):return question
    monkeypatch.setattr('bot.handlers.voice.transcribe_audio',transcribe)
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        await dp.feed_update(bot,update(1,voice=True) if mode=='voice' else update(1,text=question),config=runtime.config)
        assert counts(runtime)==(0,0)
        assert await state.get_state() is None
        assert 'čiastočné' in session.sent[-1].text
        assert 'dešifrovaná kópia sa neukladá' not in session.sent[-1].text
        assert 'bez hesla' in session.sent[-1].text
        assert not list((runtime.storage/'workspaces').rglob('archive_payloads/*'))
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


@pytest.mark.acceptance
def test_public_enqueue_error_keeps_original_and_exits_honestly(public_runtime,monkeypatch):
    runtime=public_runtime
    def fail(*args,**kwargs):raise RuntimeError('synthetic-secret-must-not-leak')
    monkeypatch.setattr('bot.services.accounting_document_archive_service.AccountingDocumentArchiveService.enqueue_confirmed_document',fail)
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        await dp.feed_update(bot,update(1,text='/add_blocek'),config=runtime.config)
        await dp.feed_update(bot,update(2,photo=True),config=runtime.config)
        await dp.feed_update(bot,update(3,text='uložiť s kategóriou'),config=runtime.config)
        assert await state.get_state() is None and session.active_keyboard is None
        assert counts(runtime)==(0,0)
        assert list((runtime.storage/'workspaces').rglob('receipts/originals/*'))
        assert 'zaradenie do archívu Google Drive zlyhalo' in session.sent[-1].text
        assert all('synthetic-secret-must-not-leak' not in m.text for m in session.sent)
        from bot.services.archive_failure_notices import deliver_failure_notices
        await deliver_failure_notices(bot=bot,db_path=runtime.database,storage_dir=runtime.storage)
        assert session.sent[-1].reply_markup is None
        assert 'archive_enqueue_failed' in session.sent[-1].text
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


@pytest.mark.acceptance
def test_background_notice_preserves_real_active_fsm_and_keyboard(public_runtime):
    from datetime import timedelta
    from tests.test_archive_delivery_v1 import NOW
    from bot.services.archive_failure_notices import deliver_failure_notices
    runtime=public_runtime
    older,source=runtime.receipt(name='older')
    worker=ArchiveWorker(runtime.database,None,storage_dir=runtime.storage)
    for i in range(5):worker.process_one(now=NOW+timedelta(minutes=15*i))
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        await dp.feed_update(bot,update(1,text='/add_blocek'),config=runtime.config)
        await dp.feed_update(bot,update(2,photo=True),config=runtime.config)
        before_state=await state.get_state();before_data=await state.get_data();before_keyboard=session.active_keyboard
        await deliver_failure_notices(bot=bot,db_path=runtime.database,storage_dir=runtime.storage,now=NOW+timedelta(hours=2))
        assert await state.get_state()==before_state
        assert await state.get_data()==before_data
        assert session.active_keyboard is before_keyboard
        assert session.sent[-1].reply_markup is None
        assert 'Počet neúspešných pokusov: 5' in session.sent[-1].text
        assert counts(runtime)==(1,1)
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


@pytest.mark.acceptance
def test_profile_switch_after_enqueue_cannot_retarget_archive(public_runtime):
    from bot.services.workspace_context import WorkspaceContextService
    runtime=public_runtime
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        await dp.feed_update(bot,update(1,text='/add_blocek'),config=runtime.config)
        await dp.feed_update(bot,update(2,photo=True),config=runtime.config)
        await dp.feed_update(bot,update(3,text='uložiť s kategóriou'),config=runtime.config)
        with sqlite3.connect(runtime.database) as c:
            c.execute("INSERT INTO workspace VALUES (?,?,?,?,?,?,?)",('synthetic-second','Second','synthetic-second-storage','Second','active','2026-01-01','2026-01-01'))
            c.execute("INSERT INTO workspace_membership VALUES (?,?,?,?,?,?)",('synthetic-second',ACTOR,'owner','active','2026-01-01','2026-01-01'))
        WorkspaceContextService(runtime.database).set_active_workspace(ACTOR,'synthetic-second')
        fake=FakeDrive()
        provider=GoogleDriveOwnerOAuthArchiveProvider(GoogleDriveOwnerOAuthClientConfig(
            db_path=runtime.database,crypto_provider=object(),owner_workspace_id='synthetic-google-owner',client_id='synthetic-client',client_secret='synthetic-secret',root_folder_id='synthetic-legacy-root'),
            drive_service=fake,media_file_upload_factory=lambda path,**kwargs:path)
        outcome=ArchiveWorker(runtime.database,provider,storage_dir=runtime.storage).process_one()
        assert outcome.status=='uploaded'
        assert runtime.store.get(outcome.job_id)['workspace_id']==WS
        assert runtime.store.get(outcome.job_id)['company_root_folder_id']=='synthetic-company-root'
        assert WorkspaceContextService(runtime.database).resolve_for_user_readonly(ACTOR).workspace_id=='synthetic-second'
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


@pytest.mark.acceptance
def test_invalid_date_upload_stays_in_intake_without_year_guess(public_runtime,monkeypatch):
    runtime=public_runtime
    async def no_date(**kwargs):return replace(_receipt_candidate(),issue_date=None)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata',no_date)
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        await dp.feed_update(bot,update(1,text='/add_blocek'),config=runtime.config)
        await dp.feed_update(bot,update(2,photo=True),config=runtime.config)
        assert await state.get_state()==AccountingDocumentIntakeStates.waiting_upload.state
        assert counts(runtime)==(0,0)
        assert not list((runtime.storage/'workspaces').rglob('years/*'))
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())
