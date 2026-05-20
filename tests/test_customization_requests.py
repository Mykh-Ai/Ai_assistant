from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bot.services import product_truth
from bot.services.customization_requests import (
    STATUS_CONFIRMED_PENDING_REVIEW,
    STATUS_DRAFT_UNCONFIRMED,
    STATUS_REVIEWED_ACCEPTED,
    CustomizationRequestService,
    hash_raw_text,
    redact_customization_request_text,
)
from bot.services.db import init_db


class CustomizationRequestServiceTests(unittest.TestCase):
    def _service(self) -> tuple[CustomizationRequestService, Path, TemporaryDirectory]:
        tmpdir = TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        db_path = Path(tmpdir.name) / 'test.sqlite3'
        init_db(db_path)
        return CustomizationRequestService(db_path), db_path, tmpdir

    def _create_request(self, service: CustomizationRequestService, **overrides):
        payload = {
            'telegram_id': 1001,
            'supplier_telegram_id': 1001,
            'source_channel': 'text',
            'source_triage_class': 'customization_request_candidate',
            'source_capability_id': 'google_drive_invoice_storage',
            'source_topic_id': 'product_capability',
            'normalized_title': 'Google Drive invoice storage',
            'normalized_summary': 'User needs generated invoices stored in Google Drive.',
            'original_user_text': 'Chcem ukladat faktury na Google Drive.',
            'confidence': 0.82,
        }
        payload.update(overrides)
        return service.create_confirmed_customization_request(**payload)

    def test_schema_bootstrap_is_idempotent(self) -> None:
        _, db_path, _ = self._service()

        init_db(db_path)
        init_db(db_path)

        connection = sqlite3.connect(db_path)
        try:
            columns = {row[1] for row in connection.execute('PRAGMA table_info(customization_requests)')}
            indexes = {row[1] for row in connection.execute('PRAGMA index_list(customization_requests)')}
        finally:
            connection.close()

        self.assertIn('request_id', columns)
        self.assertIn('telegram_id', columns)
        self.assertIn('idx_customization_requests_user_status_created', indexes)
        self.assertIn('idx_customization_requests_supplier_status_created', indexes)
        self.assertIn('idx_customization_requests_status_created', indexes)

    def test_create_confirmed_request_saves_one_row(self) -> None:
        service, _, _ = self._service()

        record = self._create_request(service, request_id='cr_known_id')
        fetched = service.get_customization_request_by_id(request_id='cr_known_id')

        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(record.request_id, 'cr_known_id')
        self.assertEqual(fetched.telegram_id, 1001)
        self.assertEqual(fetched.status, STATUS_CONFIRMED_PENDING_REVIEW)
        self.assertEqual(fetched.source_channel, 'text')
        self.assertTrue(fetched.requires_human_approval)

    def test_generated_request_ids_are_unique(self) -> None:
        service, _, _ = self._service()

        first = self._create_request(service)
        second = self._create_request(service, normalized_title='SMS reminders')

        self.assertNotEqual(first.request_id, second.request_id)

    def test_missing_telegram_id_is_rejected(self) -> None:
        service, _, _ = self._service()

        with self.assertRaisesRegex(ValueError, 'telegram_id_required'):
            self._create_request(service, telegram_id=None)

    def test_empty_title_and_summary_are_rejected(self) -> None:
        service, _, _ = self._service()

        with self.assertRaisesRegex(ValueError, 'normalized_title_required'):
            self._create_request(service, normalized_title='   ')
        with self.assertRaisesRegex(ValueError, 'normalized_summary_required'):
            self._create_request(service, normalized_summary='')

    def test_draft_unconfirmed_is_not_persisted(self) -> None:
        service, _, _ = self._service()

        with self.assertRaisesRegex(ValueError, 'draft_unconfirmed_not_persisted'):
            self._create_request(service, status=STATUS_DRAFT_UNCONFIRMED)

        self.assertEqual(service.list_customization_requests_for_user(telegram_id=1001), [])

    def test_user_listing_is_tenant_scoped(self) -> None:
        service, _, _ = self._service()

        self._create_request(service, telegram_id=1001, request_id='cr_user_a')
        self._create_request(service, telegram_id=2002, supplier_telegram_id=2002, request_id='cr_user_b')

        user_a_records = service.list_customization_requests_for_user(telegram_id=1001)
        user_b_records = service.list_customization_requests_for_user(telegram_id=2002)

        self.assertEqual([record.request_id for record in user_a_records], ['cr_user_a'])
        self.assertEqual([record.request_id for record in user_b_records], ['cr_user_b'])
        self.assertIsNone(service.get_customization_request_by_id(request_id='cr_user_b', telegram_id=1001))

    def test_list_pending_by_status_works(self) -> None:
        service, _, _ = self._service()

        pending = self._create_request(service, request_id='cr_pending')
        accepted = self._create_request(
            service,
            request_id='cr_accepted',
            status=STATUS_REVIEWED_ACCEPTED,
        )

        pending_records = service.list_pending_customization_requests()
        accepted_records = service.list_customization_requests_for_user(
            telegram_id=1001,
            status=STATUS_REVIEWED_ACCEPTED,
        )

        self.assertEqual([record.request_id for record in pending_records], [pending.request_id])
        self.assertEqual([record.request_id for record in accepted_records], [accepted.request_id])

    def test_hash_stored_but_unredacted_secret_is_not(self) -> None:
        service, _, _ = self._service()
        raw_text = (
            'Token sk-testSECRET123456789, email person@example.com, '
            'IBAN SK7700000000000000000000.'
        )

        record = self._create_request(service, request_id='cr_redacted', original_user_text=raw_text)

        self.assertEqual(record.raw_text_hash, hash_raw_text(raw_text))
        assert record.redacted_original_text is not None
        self.assertNotIn('sk-testSECRET123456789', record.redacted_original_text)
        self.assertNotIn('person@example.com', record.redacted_original_text)
        self.assertNotIn('SK7700000000000000000000', record.redacted_original_text)

    def test_redaction_removes_sensitive_values(self) -> None:
        redacted = redact_customization_request_text(
            'password=supersecret api_key abc123 token: xyz987 '
            'email test@example.com IBAN SK7700000000000000000000 phone +421 900 123 456'
        )

        assert redacted is not None
        self.assertNotIn('supersecret', redacted)
        self.assertNotIn('abc123', redacted)
        self.assertNotIn('xyz987', redacted)
        self.assertNotIn('test@example.com', redacted)
        self.assertNotIn('SK7700000000000000000000', redacted)
        self.assertNotIn('+421 900 123 456', redacted)

    def test_product_truth_is_not_mutated(self) -> None:
        service, _, _ = self._service()
        before = [entry.to_payload() for entry in product_truth.list_capabilities()]

        self._create_request(service)

        after = [entry.to_payload() for entry in product_truth.list_capabilities()]
        self.assertEqual(after, before)

    def test_no_admin_notification_hook_exists(self) -> None:
        service, _, _ = self._service()

        self.assertFalse(hasattr(service, 'send_admin_notification'))
        self.assertFalse(hasattr(service, 'notify_admin'))
        self.assertFalse(hasattr(service, 'create_code_agent_handoff'))

    def test_duplicate_request_id_is_rejected_deterministically(self) -> None:
        service, _, _ = self._service()

        self._create_request(service, request_id='cr_duplicate')
        with self.assertRaisesRegex(ValueError, 'request_id_already_exists'):
            self._create_request(service, request_id='cr_duplicate')

        records = service.list_customization_requests_for_user(telegram_id=1001)
        self.assertEqual(len(records), 1)

    def test_created_updated_and_confirmed_timestamps_are_populated(self) -> None:
        service, _, _ = self._service()

        record = self._create_request(service)

        self.assertTrue(record.created_at)
        self.assertTrue(record.updated_at)
        self.assertTrue(record.confirmed_at)
        self.assertIsNone(record.reviewed_at)

    def test_status_is_limited_to_allowed_persisted_statuses(self) -> None:
        service, _, _ = self._service()

        with self.assertRaisesRegex(ValueError, 'invalid_customization_request_status'):
            self._create_request(service, status='invented_status')

    def test_confidence_is_clamped_when_stored(self) -> None:
        service, _, _ = self._service()

        high = self._create_request(service, request_id='cr_high', confidence=9)
        low = self._create_request(service, request_id='cr_low', confidence=-2)
        bad = self._create_request(service, request_id='cr_bad', confidence='not-a-number')

        self.assertEqual(high.confidence, 1.0)
        self.assertEqual(low.confidence, 0.0)
        self.assertIsNone(bad.confidence)


if __name__ == '__main__':
    unittest.main()
