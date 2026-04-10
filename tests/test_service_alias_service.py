from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bot.services.db import init_db
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService


class ServiceAliasServiceTests(unittest.TestCase):
    def _bootstrap_services(self) -> tuple[Path, SupplierService, ServiceAliasService, int]:
        tmpdir = TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)

        db_path = Path(tmpdir.name) / 'test.sqlite3'
        init_db(db_path)

        supplier_service = SupplierService(db_path)
        supplier_service.create_or_replace(
            SupplierProfile(
                telegram_id=1001,
                name='Dodavatel s.r.o.',
                ico='12345678',
                dic='1234567890',
                ic_dph=None,
                address='Bratislava',
                iban='SK7700000000000000000000',
                swift='FIOZSKBAXXX',
                email='supplier@example.com',
                smtp_host='smtp.example.com',
                smtp_user='user',
                smtp_pass='pass',
                days_due=14,
            )
        )
        supplier = supplier_service.get_by_telegram_id(1001)
        assert supplier is not None and supplier.id is not None

        return db_path, supplier_service, ServiceAliasService(db_path), supplier.id

    def test_service_short_name_resolution_success(self) -> None:
        _, _, service_name_service, supplier_id = self._bootstrap_services()

        service_name_service.create_mapping(
            supplier_id=supplier_id,
            service_short_name='opravy',
            service_display_name='opravy vyhradených technických zariadení elektrických',
        )

        resolved = service_name_service.resolve_service_display_name(supplier_id, 'opravy')
        self.assertEqual(resolved, 'opravy vyhradených technických zariadení elektrických')

    def test_service_short_name_resolution_fallback_when_missing(self) -> None:
        _, _, service_name_service, supplier_id = self._bootstrap_services()

        resolved = service_name_service.resolve_service_display_name(supplier_id, 'unknown')
        self.assertIsNone(resolved)

    def test_service_short_name_resolution_is_case_insensitive_and_trimmed(self) -> None:
        _, _, service_name_service, supplier_id = self._bootstrap_services()

        service_name_service.create_mapping(
            supplier_id=supplier_id,
            service_short_name='Opravy',
            service_display_name='Canonical Opravy',
        )

        resolved = service_name_service.resolve_service_display_name(supplier_id, '  oPRAvy  ')
        self.assertEqual(resolved, 'Canonical Opravy')

    def test_list_mappings_hides_inactive_by_default(self) -> None:
        _, _, service_name_service, supplier_id = self._bootstrap_services()

        service_name_service.create_mapping(
            supplier_id=supplier_id,
            service_short_name='opravy',
            service_display_name='Canonical Opravy',
        )
        service_name_service.create_mapping(
            supplier_id=supplier_id,
            service_short_name='montaz',
            service_display_name='Canonical Montaz',
        )

        all_before = service_name_service.list_mappings(supplier_id)
        mapping_to_deactivate = next(entry for entry in all_before if entry.service_short_name == 'opravy')
        self.assertTrue(service_name_service.deactivate_mapping(mapping_to_deactivate.id, supplier_id))
        self.assertIsNone(service_name_service.resolve_service_display_name(supplier_id, 'opravy'))

        active_only = service_name_service.list_mappings(supplier_id)
        self.assertEqual([entry.service_short_name for entry in active_only], ['montaz'])

    def test_list_mappings_can_include_inactive_when_requested(self) -> None:
        _, _, service_name_service, supplier_id = self._bootstrap_services()

        service_name_service.create_mapping(
            supplier_id=supplier_id,
            service_short_name='opravy',
            service_display_name='Canonical Opravy',
        )

        mapping = service_name_service.list_mappings(supplier_id)[0]
        self.assertTrue(service_name_service.deactivate_mapping(mapping.id, supplier_id))

        all_entries = service_name_service.list_mappings(supplier_id, include_inactive=True)
        self.assertEqual(len(all_entries), 1)
        self.assertEqual(all_entries[0].service_short_name, 'opravy')
        self.assertEqual(all_entries[0].is_active, 0)


if __name__ == '__main__':
    unittest.main()
