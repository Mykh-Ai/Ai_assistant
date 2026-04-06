from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bot.handlers.onboarding import _normalize_optional_input
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

    def test_skip_token_and_empty_values_normalize_to_none(self) -> None:
        self.assertIsNone(_normalize_optional_input(''))
        self.assertIsNone(_normalize_optional_input('   '))
        self.assertIsNone(_normalize_optional_input('-'))
        self.assertIsNone(_normalize_optional_input('/skip'))
        self.assertEqual(_normalize_optional_input('smtp.example.com'), 'smtp.example.com')


if __name__ == '__main__':
    unittest.main()
