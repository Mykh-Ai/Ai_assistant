import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bot.services.db import init_db
from bot.services.supplier_service import SupplierProfile, SupplierService


class SupplierOptionalSmtpTests(unittest.TestCase):
    def _service(self) -> tuple[SupplierService, TemporaryDirectory]:
        tmpdir = TemporaryDirectory()
        db_path = Path(tmpdir.name) / 'test.sqlite3'
        init_db(db_path)
        return SupplierService(db_path), tmpdir

    def test_save_profile_without_smtp_fields(self) -> None:
        service, tmpdir = self._service()
        self.addCleanup(tmpdir.cleanup)

        service.create_or_replace(
            SupplierProfile(
                telegram_id=2001,
                name='No SMTP Supplier',
                ico='12345678',
                dic='1234567890',
                ic_dph=None,
                address='Bratislava',
                iban='SK7700000000000000000000',
                swift='FIOZSKBAXXX',
                email='supplier@example.com',
                smtp_host=None,
                smtp_user=None,
                smtp_pass=None,
                days_due=14,
            )
        )

        profile = service.get_by_telegram_id(2001)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertIsNone(profile.smtp_host)
        self.assertIsNone(profile.smtp_user)
        self.assertIsNone(profile.smtp_pass)
        self.assertFalse(SupplierService.has_complete_smtp_config(profile))

    def test_save_profile_with_smtp_fields_present(self) -> None:
        service, tmpdir = self._service()
        self.addCleanup(tmpdir.cleanup)

        service.create_or_replace(
            SupplierProfile(
                telegram_id=2002,
                name='SMTP Supplier',
                ico='87654321',
                dic='1234567890',
                ic_dph=None,
                address='Kosice',
                iban='SK7700000000000000000000',
                swift='FIOZSKBAXXX',
                email='supplier@example.com',
                smtp_host='smtp.example.com',
                smtp_user='smtp_user',
                smtp_pass='smtp_pass',
                days_due=30,
            )
        )

        profile = service.get_by_telegram_id(2002)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(profile.smtp_host, 'smtp.example.com')
        self.assertEqual(profile.smtp_user, 'smtp_user')
        self.assertEqual(profile.smtp_pass, 'smtp_pass')
        self.assertTrue(SupplierService.has_complete_smtp_config(profile))

    def test_init_db_migrates_legacy_smtp_not_null_columns(self) -> None:
        tmpdir = TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        db_path = Path(tmpdir.name) / 'legacy.sqlite3'

        connection = sqlite3.connect(db_path)
        try:
            connection.execute(
                """
                CREATE TABLE supplier (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    ico TEXT NOT NULL,
                    dic TEXT NOT NULL,
                    ic_dph TEXT,
                    address TEXT NOT NULL,
                    iban TEXT NOT NULL,
                    swift TEXT NOT NULL,
                    email TEXT NOT NULL,
                    smtp_host TEXT NOT NULL,
                    smtp_user TEXT NOT NULL,
                    smtp_pass TEXT NOT NULL,
                    days_due INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                (
                    'INSERT INTO supplier '
                    '(telegram_id, name, ico, dic, address, iban, swift, email, '
                    'smtp_host, smtp_user, smtp_pass, days_due) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
                ),
                (
                    2003,
                    'Legacy SMTP Supplier',
                    '12345678',
                    '1234567890',
                    'Bratislava',
                    'SK7700000000000000000000',
                    'FIOZSKBAXXX',
                    'legacy@example.com',
                    '',
                    '',
                    '',
                    14,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        init_db(db_path)

        connection = sqlite3.connect(db_path)
        try:
            column_info = {row[1]: row for row in connection.execute('PRAGMA table_info(supplier)')}
        finally:
            connection.close()
        self.assertEqual(column_info['smtp_host'][3], 0)
        self.assertEqual(column_info['smtp_user'][3], 0)
        self.assertEqual(column_info['smtp_pass'][3], 0)

        SupplierService(db_path).create_or_replace(
            SupplierProfile(
                telegram_id=2004,
                name='Migrated No SMTP Supplier',
                ico='87654321',
                dic='1234567890',
                ic_dph=None,
                address='Kosice',
                iban='SK7700000000000000000000',
                swift='FIOZSKBAXXX',
                email='migrated@example.com',
                smtp_host=None,
                smtp_user=None,
                smtp_pass=None,
                days_due=30,
            )
        )

        profile = SupplierService(db_path).get_by_telegram_id(2004)
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertIsNone(profile.smtp_host)
        self.assertIsNone(profile.smtp_user)
        self.assertIsNone(profile.smtp_pass)

    def test_skip_token_and_empty_values_normalize_to_none(self) -> None:
        self.assertIsNone(SupplierService.normalize_optional_smtp(''))
        self.assertIsNone(SupplierService.normalize_optional_smtp('   '))
        self.assertEqual(SupplierService.normalize_optional_smtp('-'), '-')
        self.assertEqual(SupplierService.normalize_optional_smtp('smtp.example.com'), 'smtp.example.com')


if __name__ == '__main__':
    unittest.main()
