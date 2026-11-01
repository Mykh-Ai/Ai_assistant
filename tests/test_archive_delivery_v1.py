"""Synthetic local integration checks, runnable with unittest or pytest."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import md5, sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sqlite3
import shutil
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, NumberObject
from reportlab.pdfgen import canvas

from bot.services import db
from bot.services.accounting_document_archive_service import AccountingDocumentArchiveService
from bot.services.archive_delivery import (
    ArchiveDeliveryError, ArchiveDeliveryStore, _unsigned_pdf, configured_route,
    prepare_payload,
)
from bot.services.archive_delivery_drive import upload_routed_file, _retryable
from bot.services.archive_failure_notices import ArchiveFailureNoticeStore, deliver_failure_notices, notice_text
from bot.services.archive_job_service import ArchiveJobService
from bot.services.archive_worker import ArchiveWorker, ArchiveUploadResult

NOW = datetime(2027, 1, 10, tzinfo=UTC)
ACTOR = 900001
WS = 'synthetic-zevs'
KEY = 'synthetic-zevs-storage'


class Request:
    def __init__(self, fn): self.fn = fn
    def execute(self): return self.fn()


class HttpFailure(Exception):
    def __init__(self, status, reason=''):
        self.resp = SimpleNamespace(status=status)
        self.content = json.dumps({'error': {'errors': [{'reason': reason}]}}).encode()


class FakeDrive:
    def __init__(self):
        self.records = {'synthetic-company-root': self.folder('synthetic-company-root', 'Company', None)}
        self.serial = 0
        self.creates = []
        self.timeout_file = False
        self.fail_create = None
    @staticmethod
    def folder(identifier, name, parent):
        return dict(id=identifier,name=name,parents=[parent] if parent else [],mimeType='application/vnd.google-apps.folder',trashed=False,capabilities={'canAddChildren':True})
    def files(self): return self
    def generateIds(self, **kwargs):
        self.serial += 1
        return Request(lambda: {'ids': ['synthetic-generated-' + str(self.serial)]})
    def get(self, fileId, **kwargs):
        def run():
            if fileId not in self.records: raise HttpFailure(404)
            return dict(self.records[fileId])
        return Request(run)
    def list(self, q, **kwargs):
        parent = re.search(r"'([^']+)' in parents", q).group(1)
        name = re.search(r"name = '([^']+)'", q).group(1)
        return Request(lambda: {'files': [dict(id=k) for k,v in self.records.items() if v.get('parents')==[parent] and v.get('name')==name and v['mimeType']=='application/vnd.google-apps.folder' and not v.get('trashed')]})
    def create(self, body, media_body=None, **kwargs):
        def run():
            if self.fail_create: raise self.fail_create
            identifier = body['id']
            if identifier in self.records: raise HttpFailure(409)
            if media_body is None:
                record = self.folder(identifier,body['name'],body['parents'][0])
            else:
                content = Path(media_body).read_bytes()
                record = dict(body,trashed=False,size=str(len(content)),md5Checksum=md5(content).hexdigest())
            self.records[identifier] = record
            self.creates.append(dict(body))
            if media_body is not None and self.timeout_file:
                self.timeout_file = False
                raise TimeoutError('synthetic indeterminate result')
            return {'id':identifier}
        return Request(run)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.storage = self.root/'storage'
        self.database = self.root/'bot.db'
        with sqlite3.connect(self.database) as c:
            for schema in (db.AUTHORIZED_USER_SCHEMA,db.SUPPLIER_SCHEMA,db.WORKSPACE_SCHEMA,db.WORKSPACE_MEMBERSHIP_SCHEMA,db.ACTIVE_WORKSPACE_SELECTION_SCHEMA):
                c.execute(schema)
            db.ensure_archive_schema(c)
            c.execute("INSERT INTO authorized_users (telegram_id,created_at) VALUES (?,?)",(ACTOR,NOW.isoformat()))
            c.execute("INSERT INTO workspace VALUES (?,?,?,?,?,?,?)",(WS,'Synthetic company',KEY,'Synthetic company','active',NOW.isoformat(),NOW.isoformat()))
            c.execute("INSERT INTO workspace_membership VALUES (?,?,?,?,?,?)",(WS,ACTOR,'owner','active',NOW.isoformat(),NOW.isoformat()))
            c.execute("INSERT INTO supplier (workspace_id,telegram_id,name,ico,dic,address,iban,swift,email,days_due) VALUES (?,?,?,?,?,?,?,?,?,?)",(WS,ACTOR,'Synthetic','00000000','0000000000','Synthetic address','synthetic-iban','synthetic-swift','synthetic@example.invalid',14))
        self.routes = self.root/'routes.json'
        self.configuration = {'schema_version':1,'routes':[
            dict(workspace_id=WS,document_type=kind,route_revision='v1',company_root_folder_id='synthetic-company-root',
                 annual_folder_template='Zevs_{YYYY}',document_folder_name=folder,relative_suffix_mode=suffix,payload_mode=mode)
            for kind,folder,suffix,mode in [('receipt','blocky','year_month','original'),('bank_statement_original','Vypisy','none','pdf_without_password')]
        ]}
        self.routes.write_text(json.dumps(self.configuration))
        self.env = patch.dict(os.environ,{'GOOGLE_DRIVE_DOCUMENT_ROUTES_FILE':str(self.routes),
            'GOOGLE_DRIVE_FAILURE_NOTICE_CUTOFF':'2026-12-01T00:00:00+00:00','GOOGLE_GMAIL_ENABLED':'0'},clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = ArchiveDeliveryStore(self.database)
        self.service = AccountingDocumentArchiveService(self.database,storage_dir=self.storage)
    def receipt(self, year=2027, month=1, name='one', base=None):
        base = base or self.storage
        folder=base/'workspaces'/KEY/'years'/str(year)/'expenses'/f'{month:02d}'/'receipts'
        source=folder/'originals'/(name+'.jpg')
        meta=folder/'metadata'/(name+'.json')
        source.parent.mkdir(parents=True,exist_ok=True); meta.parent.mkdir(parents=True,exist_ok=True)
        source.write_bytes(b'synthetic-receipt'); meta.write_text('{}')
        return self.service.enqueue_confirmed_document(workspace_id=WS,telegram_id=ACTOR,document_id=name,document_type='receipt',local_file_path=source,metadata_path=meta,
            workspace_storage_key=KEY,workspace_drive_folder_name='Synthetic company',now=NOW),source
    def statement(self, *, encrypted=True, signed=False, year=2026, month=12):
        raw=BytesIO(); paper=canvas.Canvas(raw);paper.drawString(40,750,f'Obdobie: 01.{month:02d}.{year} do 28.{month:02d}.{year}');paper.save()
        writer=PdfWriter()
        for page in PdfReader(BytesIO(raw.getvalue())).pages:writer.add_page(page)
        if signed: writer._root_object.update({NameObject('/AcroForm'):DictionaryObject({NameObject('/SigFlags'):NumberObject(3)})})
        if encrypted: writer.encrypt('synthetic-secret',owner_password='synthetic-owner')
        output=BytesIO();writer.write(output)
        directory=self.storage/'workspaces'/KEY/'bank_statement_imports'/'gmail'/'2027'/'01'/'statement-one'
        directory.mkdir(parents=True,exist_ok=True)
        source=directory/'original.pdf';source.write_bytes(output.getvalue());meta=directory/'metadata.json';meta.write_text('{}')
        result=self.service.enqueue_confirmed_document(workspace_id=WS,telegram_id=ACTOR,document_id='statement-one',document_type='bank_statement_original',local_file_path=source,metadata_path=meta,
            workspace_storage_key=KEY,workspace_drive_folder_name='Synthetic company',statement_period_year=year,statement_period_month=month,now=NOW)
        return result,source
    def upload(self,result,drive=None):
        drive=drive or FakeDrive()
        payload=prepare_payload(self.store,result.job,storage_dir=self.storage,password_loader=lambda:'synthetic-secret')
        ids=upload_routed_file(service=drive,store=self.store,context=self.store.get(result.job.job_id),local_file_path=payload,media_factory=lambda p:p)
        return drive,ids
    def test_annual_routing_is_document_based_for_2026_2027_2028(self):
        drive=FakeDrive()
        for year in (2026,2027,2028):
            result,source=self.receipt(year=year,name=str(year));self.upload(result,drive)
            context=self.store.get(result.job.job_id)
            target=drive.records[context['resolved_target_folder_id']]
            self.assertEqual(target['name'],f'{year}-01')
            annual=drive.records[drive.records[target['parents'][0]]['parents'][0]]
            self.assertEqual(annual['name'],f'Zevs_{year}')
            self.assertTrue(source.is_file())
    def test_same_folder_reused_and_immutable_route_after_config_change(self):
        drive=FakeDrive();a,_=self.receipt(name='a');self.upload(a,drive)
        b,_=self.receipt(name='b');self.upload(b,drive)
        self.assertEqual(self.store.get(a.job.job_id)['resolved_target_folder_id'],self.store.get(b.job.job_id)['resolved_target_folder_id'])
        self.configuration['routes'][0]['company_root_folder_id']='synthetic-other-root';self.routes.write_text(json.dumps(self.configuration))
        self.upload(a,drive)
        self.assertEqual(len([x for x in drive.creates if x.get('mimeType')=='application/vnd.google-apps.folder']),3)
    def test_external_tree_with_valid_workspace_suffix_is_rejected(self):
        with self.assertRaisesRegex(ArchiveDeliveryError,'archive_source_unsafe'):
            self.receipt(base=self.root/'elsewhere')
        with sqlite3.connect(self.database) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM archive_jobs').fetchone()[0],0)
    def test_worker_rejects_untrusted_storage_before_payload_write(self):
        result,_=self.statement()
        with self.assertRaisesRegex(ArchiveDeliveryError,'archive_workspace_mismatch'):
            prepare_payload(self.store,result.job,storage_dir=self.root/'elsewhere',password_loader=lambda:'synthetic-secret')
        self.assertFalse((self.storage/'workspaces'/KEY/'archive_payloads').exists())
    def test_encrypted_payload_original_and_period_preserved(self):
        result,source=self.statement();before=source.read_bytes()
        payload=prepare_payload(self.store,result.job,storage_dir=self.storage,password_loader=lambda:'synthetic-secret')
        self.assertFalse(PdfReader(payload).is_encrypted)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(payload.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.store.get(result.job.job_id)['archive_year'],2026)
        self.assertEqual(prepare_payload(self.store,result.job,storage_dir=self.storage,password_loader=lambda:None).read_bytes(),payload.read_bytes())
        with sqlite3.connect(self.database) as c:
            self.assertNotIn('synthetic-secret',repr(c.execute('SELECT * FROM archive_delivery_context').fetchall()))
    def test_password_and_signature_fail_closed(self):
        result,source=self.statement()
        for password,code in ((None,'password_required'),('wrong','password_invalid')):
            with self.assertRaisesRegex(ArchiveDeliveryError,code):
                prepare_payload(self.store,result.job,storage_dir=self.storage,password_loader=lambda:password)
        self.assertTrue(source.is_file())
        signed,_=self.statement(signed=True)
        with self.assertRaisesRegex(ArchiveDeliveryError,'signed_pdf_requires_review'):
            _unsigned_pdf(signed.job and source.read_bytes(),'synthetic-secret')
    def test_missing_payload_after_reservation_never_regenerates(self):
        result,_=self.statement();payload=prepare_payload(self.store,result.job,storage_dir=self.storage,password_loader=lambda:'synthetic-secret')
        self.store.reserve_file(result.job.job_id,'synthetic-reserved');payload.unlink()
        with self.assertRaisesRegex(ArchiveDeliveryError,'local_file_missing'):
            prepare_payload(self.store,result.job,storage_dir=self.storage,password_loader=lambda:'synthetic-secret')
    def test_timeout_reconciles_same_file_without_duplicate(self):
        result,_=self.receipt();drive=FakeDrive();drive.timeout_file=True
        self.upload(result,drive);self.upload(result,drive)
        self.assertEqual(len([x for x in drive.creates if 'appProperties' in x]),1)
    def test_remote_mismatch_is_not_overwritten(self):
        result,_=self.receipt();drive,ids=self.upload(result)
        drive.records[ids[0]]['md5Checksum']='different'
        with self.assertRaisesRegex(ArchiveDeliveryError,'archive_remote_mismatch'):self.upload(result,drive)
        self.assertEqual(len([x for x in drive.creates if 'appProperties' in x]),1)
    def test_duplicate_annual_folder_fails_closed(self):
        result,_=self.receipt();drive=FakeDrive()
        for k in ('synthetic-a','synthetic-b'):drive.records[k]=drive.folder(k,'Zevs_2027','synthetic-company-root')
        with self.assertRaisesRegex(ArchiveDeliveryError,'archive_folder_ambiguous'):self.upload(result,drive)
        self.assertFalse(drive.creates)
    def test_403_rate_limit_differs_from_permission_failure(self):
        self.assertTrue(_retryable(HttpFailure(403,'rateLimitExceeded')))
        self.assertTrue(_retryable(HttpFailure(403,'userRateLimitExceeded')))
        self.assertFalse(_retryable(HttpFailure(403,'insufficientPermissions')))
        result,_=self.receipt();drive=FakeDrive();drive.fail_create=HttpFailure(403,'rateLimitExceeded')
        with self.assertRaises(ArchiveDeliveryError) as caught:self.upload(result,drive)
        self.assertFalse(caught.exception.permanent)
        drive.fail_create=HttpFailure(403,'insufficientPermissions')
        with self.assertRaises(ArchiveDeliveryError) as caught:self.upload(result,drive)
        self.assertTrue(caught.exception.permanent)
    def test_missing_provider_exhausts_exactly_five_attempts(self):
        result,source=self.receipt()
        worker=ArchiveWorker(self.database,None,storage_dir=self.storage)
        for i in range(5):
            outcome=worker.process_one(now=NOW+timedelta(minutes=15*i))
            self.assertEqual(outcome.status,'failed' if i==4 else 'retry_wait')
        job=ArchiveJobService(self.database).get_job(result.job.job_id)
        self.assertEqual(job.attempts,5);self.assertTrue(source.exists())
        self.assertEqual(worker.process_one(now=NOW+timedelta(hours=3)).status,'noop')
    def test_terminal_failure_cleans_decrypted_payload_and_retains_original(self):
        result,source=self.statement()
        secret=self.root/'secret';secret.write_text('synthetic-secret')
        with patch.dict(os.environ,{'GOOGLE_GMAIL_STATEMENT_PDF_OPEN_PASSWORD_FILE':str(secret)}):
            worker=ArchiveWorker(self.database,None,storage_dir=self.storage)
            for i in range(5):worker.process_one(now=NOW+timedelta(minutes=15*i))
        payload=Path(self.store.get(result.job.job_id)['payload_path'])
        self.assertFalse(payload.exists());self.assertTrue(source.exists())
    def test_snapshot_job_insert_is_atomic_and_duplicate_is_stable(self):
        result,source=self.receipt();a=self.store.get(result.job.job_id)
        b,_=self.receipt();self.assertEqual(result.job.job_id,b.job.job_id)
        self.assertEqual(a,self.store.get(b.job.job_id))
        with sqlite3.connect(self.database) as c:
            before=c.execute('SELECT * FROM archive_jobs').fetchall()
            db.ensure_archive_schema(c);db.ensure_archive_schema(c)
            self.assertEqual(c.execute('SELECT * FROM archive_jobs').fetchall(),before)
    def test_route_config_invalid_never_becomes_legacy(self):
        self.routes.write_text('{"schema_version":1,"schema_version":1,"routes":[]}')
        with self.assertRaisesRegex(ArchiveDeliveryError,'archive_routes_invalid'):configured_route(WS,'receipt')
        self.assertIsNone(configured_route(WS,'incoming_invoice'))
    def test_legacy_provider_cannot_report_routed_success(self):
        result,_=self.receipt()
        class LegacyProvider:
            def upload_file(self,**kwargs):raise AssertionError('legacy uploader must not run')
        outcome=ArchiveWorker(self.database,LegacyProvider(),storage_dir=self.storage).process_one(now=NOW)
        self.assertEqual(outcome.status,'failed')
        self.assertEqual(outcome.error_code,'archive_routed_provider_unsupported')

    def test_notice_restart_delivery_retry_and_no_keyboard(self):
        result,source=self.receipt();worker=ArchiveWorker(self.database,None,storage_dir=self.storage)
        for i in range(5):worker.process_one(now=NOW+timedelta(minutes=15*i))
        store=ArchiveFailureNoticeStore(self.database);store.reconcile(now=NOW+timedelta(hours=2));store.reconcile(now=NOW+timedelta(hours=2))
        class Bot:
            def __init__(self):self.calls=[];self.fail=True
            async def send_message(self,*args,**kwargs):
                self.calls.append((args,kwargs))
                if self.fail:raise TimeoutError('synthetic Telegram timeout')
                return SimpleNamespace(message_id=123)
        bot=Bot()
        asyncio.run(deliver_failure_notices(bot=bot,db_path=self.database,storage_dir=self.storage,now=NOW+timedelta(hours=2)))
        with sqlite3.connect(self.database) as c:
            row=c.execute("SELECT status,sent_at FROM archive_failure_notices WHERE status!='activation'").fetchone()
        self.assertEqual(row,('retry_wait',None));bot.fail=False
        asyncio.run(deliver_failure_notices(bot=bot,db_path=self.database,storage_dir=self.storage,now=NOW+timedelta(hours=3)))
        asyncio.run(deliver_failure_notices(bot=bot,db_path=self.database,storage_dir=self.storage,now=NOW+timedelta(hours=4)))
        self.assertEqual(len(bot.calls),2);self.assertEqual(bot.calls[1][1],{})
        self.assertIn('5',bot.calls[1][0][1])
    def test_revoked_member_cannot_receive_notice(self):
        result,source=self.receipt();store=ArchiveFailureNoticeStore(self.database)
        store.enqueue(workspace_id=WS,recipient=ACTOR,document_id='one',error_code='archive_enqueue_failed',local_file_path=str(source),now=NOW)
        with sqlite3.connect(self.database) as c:c.execute("UPDATE workspace_membership SET status='inactive'")
        class Bot:
            async def send_message(self,*args,**kwargs):raise AssertionError('must not send')
        asyncio.run(deliver_failure_notices(bot=Bot(),db_path=self.database,storage_dir=self.storage,now=NOW))
        with sqlite3.connect(self.database) as c:self.assertEqual(c.execute("SELECT status FROM archive_failure_notices WHERE status!='activation'").fetchone()[0],'delivery_blocked')
    def test_missing_gmail_pointer_is_not_silently_lost(self):
        from bot.services.gmail_statement_collector import ensure_gmail_statement_schema
        with sqlite3.connect(self.database) as c:
            ensure_gmail_statement_schema(c)
            columns=c.execute('PRAGMA table_info(gmail_statement_imports)').fetchall()
            values={row[1]:(0 if row[2]=='INTEGER' else 'synthetic') for row in columns if row[3] and row[4] is None}
            values.update(import_id='synthetic-import',workspace_id=WS,collection_status='stored',archive_status='archive_failed',local_original_path=None,created_at=NOW.isoformat(),updated_at=NOW.isoformat())
            c.execute('INSERT INTO gmail_statement_imports ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',tuple(values.values()))
        class Bot:
            def __init__(self):self.calls=[]
            async def send_message(self,*args,**kwargs):self.calls.append((args,kwargs));return SimpleNamespace(message_id=5)
        bot=Bot()
        asyncio.run(deliver_failure_notices(bot=bot,db_path=self.database,storage_dir=self.storage,now=NOW))
        self.assertEqual(len(bot.calls),1)
        self.assertIn('originál nie je dostupný',bot.calls[0][0][1])
        self.assertNotIn('zostal zachovaný',bot.calls[0][0][1])
    def test_transient_authority_lookup_retries_instead_of_blocking(self):
        result,source=self.receipt();store=ArchiveFailureNoticeStore(self.database)
        store.enqueue(workspace_id=WS,recipient=ACTOR,document_id='one',error_code='archive_enqueue_failed',local_file_path=str(source),now=NOW)
        with patch('bot.services.archive_failure_notices.WorkspaceContextService.require_membership',side_effect=sqlite3.OperationalError('synthetic temporarily locked')):
            asyncio.run(deliver_failure_notices(bot=object(),db_path=self.database,storage_dir=self.storage,now=NOW))
        with sqlite3.connect(self.database) as c:
            self.assertEqual(c.execute("SELECT status FROM archive_failure_notices WHERE status!='activation'").fetchone()[0],'retry_wait')

    @unittest.skipUnless(shutil.which('pdftoppm'), 'pdftoppm not available')
    def test_rendered_statement_page_is_identical(self):
        result,source=self.statement()
        payload=prepare_payload(self.store,result.job,storage_dir=self.storage,password_loader=lambda:'synthetic-secret')
        outputs=[]
        for path,label,password in ((source,'source','synthetic-secret'),(payload,'copy',None)):
            prefix=self.root/label
            command=['pdftoppm','-r','72','-f','1','-singlefile','-png']
            if password:command+=['-upw',password]
            subprocess.run(command+[str(path),str(prefix)],check=True,capture_output=True)
            outputs.append(prefix.with_suffix('.png').read_bytes())
        self.assertEqual(sha256(outputs[0]).hexdigest(),sha256(outputs[1]).hexdigest())

    def test_context_probe_does_not_create_missing_database(self):
        missing=self.root/'not-created.sqlite3'
        self.assertIsNone(ArchiveDeliveryStore(missing).get('synthetic-job'))
        self.assertFalse(missing.exists())

    def test_wrong_secret_worker_notifies_without_upload(self):
        result,source=self.statement()
        class Provider:
            supports_routed_delivery=True
            def upload_file(self,**kwargs):raise AssertionError('password failure must not upload')
        with patch.dict(os.environ,{'GOOGLE_GMAIL_STATEMENT_PDF_OPEN_PASSWORD_FILE':str(self.root/'missing-secret')}):
            outcome=ArchiveWorker(self.database,Provider(),storage_dir=self.storage).process_one(now=NOW)
        self.assertEqual(outcome.status,'failed')
        self.assertEqual(outcome.error_code,'password_secret_unavailable')
        self.assertTrue(source.is_file())
        class Bot:
            def __init__(self):self.calls=[]
            async def send_message(self,*args,**kwargs):self.calls.append((args,kwargs));return SimpleNamespace(message_id=7)
        bot=Bot()
        asyncio.run(deliver_failure_notices(bot=bot,db_path=self.database,storage_dir=self.storage,now=NOW))
        self.assertEqual(len(bot.calls),1)
        self.assertIn('password_secret_unavailable',bot.calls[0][0][1])
        self.assertNotIn('synthetic-secret',bot.calls[0][0][1])
        self.assertNotIn('Počet neúspešných pokusov: 5',bot.calls[0][0][1])

    def test_rollout_audit_is_read_only_and_blocks_legacy_jobs(self):
        from bot.cli.archive_delivery_audit import audit
        with patch.dict(os.environ,{'GOOGLE_DRIVE_DOCUMENT_ROUTES_FILE':''}):
            result,source=self.receipt()
        before=sha256(self.database.read_bytes()).hexdigest()
        report=audit(self.database)
        after=sha256(self.database.read_bytes()).hexdigest()
        self.assertEqual(before,after)
        self.assertEqual(report['integrity'],'ok')
        self.assertEqual(len(report['activation_blockers']),1)
        self.assertNotIn(result.job.job_id,json.dumps(report))

    def test_missing_original_message_is_honest_and_cutoff_frozen(self):
        result,source=self.receipt();store=ArchiveFailureNoticeStore(self.database)
        store.enqueue(workspace_id=WS,recipient=ACTOR,document_id='one',error_code='local_file_missing',local_file_path=str(source),now=NOW)
        notice=store.claim(now=NOW);source.unlink()
        self.assertNotIn('zostal zachovaný',notice_text(notice,source_present=False))
        with patch.dict(os.environ,{'GOOGLE_DRIVE_FAILURE_NOTICE_CUTOFF':'2026-11-01T00:00:00+00:00'}):
            with self.assertRaisesRegex(ValueError,'archive_notice_cutoff_changed'):store.claim(now=NOW)


if __name__ == '__main__':unittest.main()
