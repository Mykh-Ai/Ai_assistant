"""Local concurrency, process-termination and cross-flow acceptance boundaries.

All Google/Telegram/model transports are synthetic. Child processes only write
into pytest temporary storage and a fake-send log; no network or credentials.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
from threading import Barrier, Lock, RLock
from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.methods import EditMessageReplyMarkup

from bot.handlers.invoice import InvoiceStates
from bot.handlers.work_time import WorkTimeStates
from bot.services.archive_delivery import ArchiveDeliveryStore, prepare_payload
from bot.services.archive_failure_notices import ArchiveFailureNoticeStore, deliver_failure_notices
from bot.services.archive_worker import ArchiveWorker
from bot.services.token_crypto import TokenCryptoError
from tests.test_archive_delivery_edge_cases import provider
from tests.test_archive_delivery_public_journeys import public_runtime, dispatcher, LocalSession, update, counts
from tests.test_archive_delivery_v1 import ACTOR, WS, NOW, FakeDrive, Request
from tests.test_accounting_document_intake_flow import _receipt_candidate


class LockedDrive(FakeDrive):
    """Atomic fake remote operations; real SQLite reservations arbitrate workers."""
    def __init__(self):
        super().__init__()
        self.lock=RLock()

    def generateIds(self, **kwargs):
        def execute():
            with self.lock:
                self.serial+=1
                return {'ids':['synthetic-generated-'+str(self.serial)]}
        return Request(execute)

    def get(self, **kwargs):return self._locked(super().get(**kwargs))
    def list(self, **kwargs):return self._locked(super().list(**kwargs))
    def create(self, **kwargs):return self._locked(super().create(**kwargs))
    def _locked(self, request):
        def execute():
            with self.lock:return request.execute()
        return Request(execute)


def test_two_transient_file_errors_then_third_verified_success(public_runtime):
    runtime=public_runtime
    job,source=runtime.receipt();fake=FakeDrive();create=fake.create;attempts=[]
    def flaky(body,media_body=None,**kwargs):
        if media_body is not None:
            attempts.append((body['id'],Path(media_body).read_bytes()))
            if len(attempts)<=2:return Request(lambda:(_ for _ in ()).throw(TimeoutError('synthetic file timeout')))
        return create(body=body,media_body=media_body,**kwargs)
    fake.create=flaky
    for i,expected in enumerate(['retry_wait','retry_wait','uploaded']):
        # Fresh worker/store/provider simulates normal process restart each tick.
        outcome=ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW+timedelta(minutes=15*i))
        assert outcome.status==expected
    assert len(attempts)==3 and len({x[0] for x in attempts})==1
    assert all(x[1]==source.read_bytes() for x in attempts)
    assert len([x for x in fake.creates if 'appProperties' in x])==1
    with sqlite3.connect(runtime.database) as c:
        assert c.execute('SELECT status,attempts FROM archive_jobs').fetchone()==('uploaded',2) # existing counter records failed attempts
    ArchiveFailureNoticeStore(runtime.database).reconcile(now=NOW+timedelta(hours=1))
    with sqlite3.connect(runtime.database) as c:
        assert c.execute("SELECT count(*) FROM archive_failure_notices WHERE status!='activation'").fetchone()[0]==0


def test_concurrent_annual_type_month_reservations_create_one_tree(public_runtime,monkeypatch):
    import bot.services.archive_delivery_drive as drive
    runtime=public_runtime;fake=LockedDrive()
    jobs=[runtime.receipt(name=name)[0] for name in ('concurrent-a','concurrent-b')]
    payloads=[prepare_payload(runtime.store,x.job,storage_dir=runtime.storage) for x in jobs]
    reserve=drive._reserve_folder;guard=Lock();barriers={};calls={}
    def competing(store,context,path,proposed,parent):
        with guard:
            barrier=barriers.setdefault(path,Barrier(2,timeout=10))
            calls[path]=calls.get(path,0)+1
        barrier.wait()
        return reserve(store,context,path,proposed,parent)
    monkeypatch.setattr(drive,'_reserve_folder',competing)
    def upload(index):
        store=ArchiveDeliveryStore(runtime.database)
        return drive.upload_routed_file(service=fake,store=store,context=store.get(jobs[index].job.job_id),
            local_file_path=payloads[index],media_factory=lambda path:path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(upload,range(2)))
    assert len(calls)==3 and set(calls.values())=={2}
    assert results[0][1]==results[1][1] and results[0][0]!=results[1][0]
    assert sorted(x['name'] for x in fake.creates if 'appProperties' not in x)==['2027-01','Zevs_2027','blocky']
    assert len([x for x in fake.creates if 'appProperties' in x])==2
    with sqlite3.connect(runtime.database) as c:
        assert c.execute('SELECT count(*) FROM google_drive_folder_cache').fetchone()[0]==3


@pytest.mark.parametrize('folder',['Zevs_2027','blocky','2027-01'])
def test_each_folder_timeout_recovers_persisted_id_in_new_worker(public_runtime,folder):
    runtime=public_runtime;job,source=runtime.receipt();fake=FakeDrive();create=fake.create;timed_out=[]
    def indeterminate(body,**kwargs):
        request=create(body=body,**kwargs)
        def execute():
            result=request.execute()
            if body['name']==folder and not timed_out:
                timed_out.append(body['id']);raise TimeoutError('synthetic indeterminate folder')
            return result
        return Request(execute)
    fake.create=indeterminate
    assert ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW).status=='retry_wait'
    with sqlite3.connect(runtime.database) as c:
        assert c.execute('SELECT folder_id FROM google_drive_folder_cache WHERE folder_id=?',(timed_out[0],)).fetchone()==(timed_out[0],)
    assert ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW+timedelta(minutes=15)).status=='uploaded'
    assert len([x for x in fake.creates if x['name']==folder])==1
    assert source.is_file()


@pytest.mark.parametrize('folder',['Zevs_2027','blocky','2027-01'])
@pytest.mark.parametrize('field,value',[('parents',['synthetic-foreign-parent']),('trashed',True),('capabilities',{'canAddChildren':False})])
def test_cached_folder_lineage_or_permission_change_fails_closed(public_runtime,folder,field,value):
    runtime=public_runtime;fake=FakeDrive();runtime.receipt(name='first')
    assert ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW).status=='uploaded'
    identifier=next(key for key,row in fake.records.items() if row['name']==folder)
    fake.records[identifier][field]=value
    second,source=runtime.receipt(name='second')
    before=len(fake.creates)
    outcome=ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW)
    assert outcome.job_id==second.job.job_id and outcome.status=='failed'
    assert outcome.error_code in {'archive_folder_mismatch','archive_folder_forbidden'}
    assert len(fake.creates)==before and source.is_file()


def test_enabled_provider_builder_none_has_bounded_lifecycle_and_notice(public_runtime,monkeypatch):
    import bot.services.google_drive_archive_scheduler as scheduler
    runtime=public_runtime;job,source=runtime.receipt();builds=[]
    def unavailable(config):
        builds.append(1);raise TokenCryptoError('synthetic crypto unavailable')
    monkeypatch.setattr(scheduler,'build_google_token_crypto_provider',unavailable)
    for i in range(5):
        outcome=scheduler.process_google_drive_archive_once(config=runtime.config,now=NOW+timedelta(minutes=15*i))
        assert outcome.status==('failed' if i==4 else 'retry_wait')
    assert len(builds)==5 and source.is_file()
    class FakeBot:
        def __init__(self):self.calls=[]
        async def send_message(self,*args,**kwargs):self.calls.append((args,kwargs));return SimpleNamespace(message_id=1)
    bot=FakeBot()
    asyncio.run(deliver_failure_notices(bot=bot,db_path=runtime.database,storage_dir=runtime.storage,now=NOW+timedelta(hours=2)))
    assert len(bot.calls)==1 and 'Počet neúspešných pokusov: 5' in bot.calls[0][0][1]
    assert bot.calls[0][1]=={}


# Intentionally kill only the synthetic child, never the test runner.
_CHILD = '''
import asyncio,json,os,signal,sys
from datetime import datetime
from pathlib import Path
from bot.services.archive_failure_notices import ArchiveFailureNoticeStore,deliver_failure_notices
mode,db,storage,log,timestamp=sys.argv[1:]
class FakeBot:
    async def send_message(self,*args,**kwargs):
        assert not kwargs
        with open(log,'a') as handle:
            handle.write(json.dumps(args)+'\\n');handle.flush();os.fsync(handle.fileno())
        return type('Sent',(),{'message_id':1})()
original=ArchiveFailureNoticeStore.complete
def complete(self,*args,**kwargs):
    if mode=='after_ack':original(self,*args,**kwargs)
    os.kill(os.getpid(),signal.SIGKILL)
if mode!='normal':ArchiveFailureNoticeStore.complete=complete
asyncio.run(deliver_failure_notices(bot=FakeBot(),db_path=Path(db),storage_dir=Path(storage),now=datetime.fromisoformat(timestamp)))
'''


@pytest.mark.parametrize('mode',['before_ack','after_ack'])
def test_actual_child_sigkill_notice_restarts_without_upload_retry(public_runtime,mode):
    runtime=public_runtime;job,source=runtime.receipt();log=runtime.root/'fake-telegram-sends.jsonl'
    ArchiveFailureNoticeStore(runtime.database).enqueue(workspace_id=WS,recipient=ACTOR,document_id='one',
        error_code='archive_enqueue_failed',local_file_path=str(source),now=NOW)
    def child(mode,at):
        return subprocess.run([sys.executable,'-c',_CHILD,mode,str(runtime.database),str(runtime.storage),str(log),at.isoformat()],
            cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
    first=child(mode,NOW)
    assert first.returncode==-signal.SIGKILL,first.stderr
    with sqlite3.connect(runtime.database) as c:
        row=c.execute("SELECT event_key,status,sent_at FROM archive_failure_notices WHERE status!='activation'").fetchone()
    assert row[1]==('sending' if mode=='before_ack' else 'sent')
    assert (row[2] is None)==(mode=='before_ack')
    assert len(log.read_text().splitlines())==1
    for minutes in (1,6,12):
        result=child('normal',NOW+timedelta(minutes=minutes));assert result.returncode==0,result.stderr
        if minutes==1:assert len(log.read_text().splitlines())==1
    sends=[json.loads(line) for line in log.read_text().splitlines()]
    assert len(sends)==(2 if mode=='before_ack' else 1)
    assert all(value==sends[0] for value in sends)
    with sqlite3.connect(runtime.database) as c:
        assert c.execute("SELECT event_key,status FROM archive_failure_notices WHERE status!='activation'").fetchone()==(row[0],'sent')
        assert c.execute('SELECT status,attempts FROM archive_jobs').fetchone()==('pending',0)


@pytest.mark.parametrize('flow',['work_time','invoice'])
def test_notice_preserves_public_work_time_or_invoice_fsm(public_runtime,monkeypatch,flow):
    runtime=public_runtime;job,source=runtime.receipt()
    ArchiveFailureNoticeStore(runtime.database).enqueue(workspace_id=WS,recipient=ACTOR,document_id='one',
        error_code='archive_enqueue_failed',local_file_path=str(source),now=NOW)
    async def primary(**kwargs):
        kwargs['diagnostics']['slots']={'period':{'type':'month','year':2026,'month':12}}
        return 'generate_work_time_report'
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action',primary)
    class Session(LocalSession):
        def __init__(self):super().__init__();self.edits=[]
        async def make_request(self,bot,method,timeout=None):
            if isinstance(method,EditMessageReplyMarkup):self.edits.append(method);return True
            return await super().make_request(bot,method,timeout)
    async def journey():
        session=Session();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        await dp.feed_update(bot,update(1,text='Vytvor výkaz za december 2026' if flow=='work_time' else '/invoice'),config=runtime.config)
        assert await state.get_state()==(WorkTimeStates.waiting_lunch_break_initial_choice.state if flow=='work_time' else InvoiceStates.waiting_input.state)
        before_state=await state.get_state();before_data=await state.get_data();before_markup=session.sent[-1].reply_markup
        await deliver_failure_notices(bot=bot,db_path=runtime.database,storage_dir=runtime.storage,now=NOW)
        assert await state.get_state()==before_state and await state.get_data()==before_data
        assert session.sent[-1].reply_markup is None and session.edits==[]
        if flow=='work_time':assert before_markup.inline_keyboard
        assert counts(runtime)==(1,1)
        await dp.feed_update(bot,update(2,text='/cancel'),config=runtime.config)
        assert await state.get_state() is None
        if flow=='work_time':assert session.edits[-1].reply_markup is None
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())


def test_calendar_edge_reupload_continuation_uses_document_date(public_runtime,monkeypatch):
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates
    import bot.services.archive_job_service as archive
    runtime=public_runtime;extractions=[]
    async def extract(**kwargs):
        extractions.append(1)
        return replace(_receipt_candidate(),issue_date=None if len(extractions)==1 else '2026-12-31')
    class JanuaryClock(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2027,1,1,0,5,tzinfo=UTC)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata',extract)
    monkeypatch.setattr(archive,'datetime',JanuaryClock)
    async def journey():
        session=LocalSession();bot=Bot(runtime.config.bot_token,session=session);dp=dispatcher()
        state=dp.fsm.get_context(bot=bot,chat_id=ACTOR,user_id=ACTOR)
        await dp.feed_update(bot,update(1,text='/add_blocek'),config=runtime.config)
        await dp.feed_update(bot,update(2,photo=True),config=runtime.config)
        assert await state.get_state()==AccountingDocumentIntakeStates.waiting_upload.state
        assert counts(runtime)==(0,0)
        await dp.feed_update(bot,update(3,text='31.12.2026'),config=runtime.config)
        assert await state.get_state()==AccountingDocumentIntakeStates.waiting_upload.state
        assert counts(runtime)==(0,0) # continuation remains a file, never an idle write
        await dp.feed_update(bot,update(4,photo=True),config=runtime.config)
        assert await state.get_state()==AccountingDocumentIntakeStates.waiting_preview_decision.state
        await dp.feed_update(bot,update(5,text='uložiť s kategóriou'),config=runtime.config)
        assert await state.get_state() is None and counts(runtime)==(1,1)
        with sqlite3.connect(runtime.database) as c:job=c.execute('SELECT job_id,created_at FROM archive_jobs').fetchone()
        assert job[1].startswith('2027-01-01')
        context=runtime.store.get(job[0]);assert (context['archive_year'],context['archive_month'])==(2026,12)
        fake=FakeDrive()
        assert ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW).status=='uploaded'
        assert any(row['name']=='2026-12' for row in fake.records.values())
        assert not any(row['name']=='Zevs_2027' for row in fake.records.values())
        assert session.sent[-1].reply_markup.remove_keyboard is True
        await bot.session.close();await dp.storage.close()
    asyncio.run(journey())
