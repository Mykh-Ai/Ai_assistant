from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from bot.services.archive_delivery import ArchiveDeliveryError, prepare_payload, _unsigned_pdf
from bot.services.archive_worker import ArchiveWorker
from bot.services.archive_failure_notices import ArchiveFailureNoticeStore, deliver_failure_notices
from bot.services.google_drive_owner_oauth_client import GoogleDriveOwnerOAuthArchiveProvider, GoogleDriveOwnerOAuthClientConfig
from tests.test_archive_delivery_v1 import ACTOR, WS, NOW, FakeDrive, Request
from tests.test_archive_delivery_public_journeys import public_runtime
from tests.test_gmail_statement_period import _encrypted_pdf, _pdf_with_text
from tests.test_gmail_statement_collector import Transport, message_payload


def provider(runtime, fake):
    return GoogleDriveOwnerOAuthArchiveProvider(GoogleDriveOwnerOAuthClientConfig(
        db_path=runtime.database,crypto_provider=object(),owner_workspace_id='synthetic-google-owner',
        client_id='synthetic-client',client_secret='synthetic-client-secret',root_folder_id='synthetic-legacy-root'),
        drive_service=fake,media_file_upload_factory=lambda path,**kwargs:path)


def test_folder_pagination_reuses_existing_id(public_runtime):
    runtime=public_runtime
    fake=FakeDrive();one,_=runtime.receipt(name='one');runtime.upload(one,fake)
    original=fake.list;pages=[]
    def paginated(q,**kwargs):
        if "name = 'Zevs_2027'" in q:
            pages.append(kwargs.get('pageToken'))
            if not kwargs.get('pageToken'):return Request(lambda:{'files':[],'nextPageToken':'synthetic-next'})
        return original(q=q,**kwargs)
    fake.list=paginated
    two,_=runtime.receipt(name='two');runtime.upload(two,fake)
    assert pages==[None,'synthetic-next']
    assert runtime.store.get(one.job.job_id)['resolved_target_folder_id']==runtime.store.get(two.job.job_id)['resolved_target_folder_id']


def test_folder_timeout_reuses_persisted_reservation(public_runtime):
    runtime=public_runtime
    fake=FakeDrive();original=fake.create;first=[True]
    def timeout_create(body,**kwargs):
        request=original(body=body,**kwargs)
        def execute():
            value=request.execute()
            if body.get('name')=='Zevs_2027' and first[0]:
                first[0]=False
                raise TimeoutError('synthetic folder create timeout')
            return value
        return Request(execute)
    fake.create=timeout_create
    job,source=runtime.receipt()
    worker=ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage)
    assert worker.process_one(now=NOW).status=='retry_wait'
    created=[x for x in fake.creates if x['name']=='Zevs_2027']
    assert len(created)==1
    reserved=created[0]['id']
    with sqlite3.connect(runtime.database) as c:
        assert c.execute('SELECT folder_id FROM google_drive_folder_cache WHERE folder_id=?',(reserved,)).fetchone()==(reserved,)
    assert worker.process_one(now=NOW+timedelta(minutes=15)).status=='uploaded'
    assert len([x for x in fake.creates if x['name']=='Zevs_2027'])==1
    assert source.is_file()


def test_retry_crossing_new_year_keeps_original_period(public_runtime):
    runtime=public_runtime
    job,source=runtime.receipt(year=2026,month=12)
    before=datetime(2026,12,31,23,55,tzinfo=UTC)
    assert ArchiveWorker(runtime.database,None,storage_dir=runtime.storage).process_one(now=before).status=='retry_wait'
    fake=FakeDrive()
    after=datetime(2027,1,1,0,10,tzinfo=UTC)
    assert ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=after).status=='uploaded'
    context=runtime.store.get(job.job.job_id)
    assert context['archive_year']==2026 and context['archive_month']==12
    assert any(x['name']=='Zevs_2026' for x in fake.records.values())
    assert not any(x['name']=='Zevs_2027' for x in fake.records.values())


@pytest.mark.parametrize('field,value',[
    ('parents',['synthetic-foreign-folder']),('size','999999'),
    ('appProperties',{'archive_delivery_ref':'synthetic-wrong-reference'}),('md5Checksum','synthetic-wrong-checksum')])
def test_remote_mismatch_fails_worker_without_overwrite(public_runtime,field,value):
    runtime=public_runtime
    job,source=runtime.receipt();fake,ids=runtime.upload(job)
    fake.records[ids[0]][field]=value
    outcome=ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW)
    assert outcome.status=='failed' and outcome.error_code=='archive_remote_mismatch'
    assert source.is_file()
    assert len([x for x in fake.creates if 'appProperties' in x])==1


def test_unencrypted_statement_does_not_read_secret(public_runtime):
    runtime=public_runtime
    job,source=runtime.statement(encrypted=False)
    def forbidden():raise AssertionError('plaintext PDF must not load a secret')
    payload=prepare_payload(runtime.store,job.job,storage_dir=runtime.storage,password_loader=forbidden)
    assert payload.read_bytes()==source.read_bytes()
    assert PdfReader(payload).is_encrypted is False


def test_corrupt_statement_fails_closed_without_secret_read():
    with pytest.raises(ArchiveDeliveryError,match='pdf_unreadable'):_unsigned_pdf(b'%PDF-corrupt',None)


@pytest.mark.parametrize('secret_mode,period_year',[('missing',2026),('wrong',2026),('valid',2026),('plaintext',2027),('ambiguous',2027),('unsupported',2027),('no_text',2027)])
def test_real_gmail_tick_secret_failure_or_verified_upload(public_runtime,monkeypatch,secret_mode,period_year):
    import bot.services.gmail_statement_scheduler as scheduler
    runtime=public_runtime
    content=_encrypted_pdf(f'Obdobie: 01.09.{period_year} do 30.09.{period_year}',user='synthetic-opening',owner='synthetic-owner')
    if secret_mode=='plaintext':content=_pdf_with_text(f'Obdobie: 01.01.{period_year} do 31.01.{period_year}')
    elif secret_mode=='ambiguous':content=_pdf_with_text('Datum 31.12.2026\nDatum 31.01.2027\nPosledny vypis 30.11.2026')
    elif secret_mode=='unsupported':content=content.replace(b'/V 2',b'/V 9')
    elif secret_mode=='no_text':content=_pdf_with_text('')
    message=message_payload();message['payload']['parts']=message['payload']['parts'][1:2]
    message['payload']['parts'][0]['body']['size']=len(content)
    class FakeTransport(Transport):
        def get_attachment(self,*args):return base64.urlsafe_b64encode(content).decode()
    transport=FakeTransport(message)
    secret=runtime.root/'gmail-secret'
    if secret_mode not in {'missing','plaintext'}:secret.write_text('synthetic-wrong' if secret_mode=='wrong' else 'synthetic-opening')
    gmail=SimpleNamespace(target_workspace_id=WS,token_crypto_secret='synthetic-token-secret',
        statement_pdf_open_password_file=str(secret),client_id='synthetic-client',client_secret='synthetic-client-secret',
        statement_query='from:synthetic@example.invalid has:attachment',batch_size=10,initial_lookback_days=30,overlap_hours=24,
        max_attachment_bytes=100000,allowed_mime_types=frozenset({'application/pdf'}),allowed_extensions=frozenset({'.pdf'}))
    class Runtime:
        def load_active_grant(self,*args):return SimpleNamespace(access_token='synthetic-token',refresh_token='synthetic-refresh',connection_id='synthetic-grant',scopes=('https://www.googleapis.com/auth/gmail.readonly',))
        def last_successful_check(self,*args):return None
        def mark_check_succeeded(self,*args):pass
    monkeypatch.setattr(scheduler,'load_google_gmail_config',lambda:gmail)
    monkeypatch.setattr(scheduler,'GoogleGmailRuntimeService',lambda *args:Runtime())
    monkeypatch.setattr(scheduler,'FernetTokenCryptoProvider',lambda **kwargs:object())
    monkeypatch.setattr(scheduler,'GoogleAPIGmailReadonlyTransport',lambda **kwargs:transport)
    outcome,result,workspace=scheduler._run_tick(runtime.config)
    assert outcome=='complete' and result.stored==1
    imported=result.new_imports[0];source=Path(imported.local_original_path)
    assert source.read_bytes()==content
    with sqlite3.connect(runtime.database) as c:
        jobs=c.execute('SELECT count(*) FROM archive_jobs').fetchone()[0]
    if secret_mode not in {'valid','plaintext'}:
        assert jobs==0
        class Bot:
            def __init__(self):self.calls=[]
            async def send_message(self,*args,**kwargs):self.calls.append((args,kwargs));return SimpleNamespace(message_id=10)
        bot=Bot();asyncio.run(deliver_failure_notices(bot=bot,db_path=runtime.database,storage_dir=runtime.storage))
        assert len(bot.calls)==1
        expected={'missing':'password_secret_unavailable','wrong':'password_invalid','ambiguous':'period_ambiguous','unsupported':'pdf_unreadable','no_text':'text_unavailable'}[secret_mode]
        assert expected in bot.calls[0][0][1]
        assert 'synthetic-opening' not in bot.calls[0][0][1]
        assert bot.calls[0][1]=={}
    else:
        assert jobs==1 and imported.statement_period_year==period_year
        assert imported.statement_period_month==(1 if secret_mode=='plaintext' else 9)
        monkeypatch.setenv('GOOGLE_GMAIL_STATEMENT_PDF_OPEN_PASSWORD_FILE',str(secret))
        fake=FakeDrive();captured=[];original=fake.create
        def capture(body,media_body=None,**kwargs):
            if media_body is not None:captured.append(Path(media_body).read_bytes())
            return original(body=body,media_body=media_body,**kwargs)
        fake.create=capture
        worker=ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage)
        uploaded=worker.process_one()
        assert uploaded.status=='uploaded'
        assert PdfReader(BytesIO(captured[0])).is_encrypted is False
        context=runtime.store.get(uploaded.job_id)
        target=fake.records[context['resolved_target_folder_id']]
        assert target['name']=='Vypisy'
        assert fake.records[target['parents'][0]]['name']==f'Zevs_{period_year}'
        assert source.read_bytes()==content
        assert not Path(context['payload_path']).exists()


def test_notice_scheduler_runs_while_upload_disabled(public_runtime,monkeypatch):
    import bot.services.google_drive_archive_scheduler as scheduler
    runtime=public_runtime
    job,source=runtime.receipt()
    ArchiveFailureNoticeStore(runtime.database).enqueue(workspace_id=WS,recipient=ACTOR,document_id='one',
        error_code='archive_disabled',local_file_path=str(source))
    class Bot:
        def __init__(self):self.calls=[]
        async def send_message(self,*args,**kwargs):self.calls.append((args,kwargs));return SimpleNamespace(message_id=12)
    bot=Bot()
    async def stop(*args):raise asyncio.CancelledError
    monkeypatch.setattr(scheduler.asyncio,'sleep',stop)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_google_drive_archive_scheduler(config=replace(runtime.config,google_drive_enabled=False),bot=bot))
    assert len(bot.calls)==1 and bot.calls[0][1]=={}
    with sqlite3.connect(runtime.database) as c:
        assert c.execute('SELECT status FROM archive_jobs').fetchone()[0]=='pending'
    assert source.is_file()


def test_missing_source_worker_notifies_without_false_retention(public_runtime):
    runtime=public_runtime
    job,source=runtime.receipt();source.unlink()
    fake=FakeDrive()
    outcome=ArchiveWorker(runtime.database,provider(runtime,fake),storage_dir=runtime.storage).process_one(now=NOW)
    assert outcome.status=='failed' and outcome.error_code=='local_file_missing'
    assert not fake.creates
    class Bot:
        def __init__(self):self.calls=[]
        async def send_message(self,*args,**kwargs):self.calls.append(args);return SimpleNamespace(message_id=22)
    bot=Bot();asyncio.run(deliver_failure_notices(bot=bot,db_path=runtime.database,storage_dir=runtime.storage,now=NOW))
    assert len(bot.calls)==1 and 'originál nie je dostupný' in bot.calls[0][1]
    assert 'zostal zachovaný' not in bot.calls[0][1]


def test_actual_forbidden_error_blocks_delivery_without_upload_retry(public_runtime):
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import SendMessage
    runtime=public_runtime
    job,source=runtime.receipt()
    store=ArchiveFailureNoticeStore(runtime.database)
    store.enqueue(workspace_id=WS,recipient=ACTOR,document_id='one',error_code='archive_enqueue_failed',local_file_path=str(source))
    class Bot:
        async def send_message(self,*args,**kwargs):
            raise TelegramForbiddenError(method=SendMessage(chat_id=ACTOR,text='synthetic'),message='synthetic blocked')
    asyncio.run(deliver_failure_notices(bot=Bot(),db_path=runtime.database,storage_dir=runtime.storage))
    with sqlite3.connect(runtime.database) as c:
        assert c.execute("SELECT status,sent_at FROM archive_failure_notices WHERE status!='activation'").fetchone()==('delivery_blocked',None)
        assert c.execute('SELECT status,attempts FROM archive_jobs').fetchone()==('pending',0)
