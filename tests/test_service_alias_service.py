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

    def test_alias_resolution_success(self) -> None:
        _, _, alias_service, supplier_id = self._bootstrap_services()

        alias_service.create_mapping(
            supplier_id=supplier_id,
            alias='opravy',
            canonical_title='opravy vyhradených technických zariadení elektrických',
        )

        resolved = alias_service.resolve_alias(supplier_id, 'opravy')
        self.assertEqual(resolved, 'opravy vyhradených technických zariadení elektrických')

    def test_alias_resolution_fallback_when_missing(self) -> None:
        _, _, alias_service, supplier_id = self._bootstrap_services()

        resolved = alias_service.resolve_alias(supplier_id, 'unknown')
        self.assertIsNone(resolved)

    def test_alias_resolution_is_case_insensitive_and_trimmed(self) -> None:
        _, _, alias_service, supplier_id = self._bootstrap_services()

        alias_service.create_mapping(
            supplier_id=supplier_id,
            alias='Opravy',
            canonical_title='Canonical Opravy',
        )

        resolved = alias_service.resolve_alias(supplier_id, '  oPRAvy  ')
        self.assertEqual(resolved, 'Canonical Opravy')

    def test_list_mappings_hides_inactive_by_default(self) -> None:
        _, _, alias_service, supplier_id = self._bootstrap_services()

        alias_service.create_mapping(
            supplier_id=supplier_id,
            alias='opravy',
            canonical_title='Canonical Opravy',
        )
        alias_service.create_mapping(
            supplier_id=supplier_id,
            alias='montaz',
            canonical_title='Canonical Montaz',
        )

        all_before = alias_service.list_mappings(supplier_id)
        mapping_to_deactivate = next(entry for entry in all_before if entry.alias == 'opravy')
        self.assertTrue(alias_service.deactivate_mapping(mapping_to_deactivate.id, supplier_id))
        self.assertIsNone(alias_service.resolve_alias(supplier_id, 'opravy'))

        active_only = alias_service.list_mappings(supplier_id)
        self.assertEqual([entry.alias for entry in active_only], ['montaz'])

    def test_list_mappings_can_include_inactive_when_requested(self) -> None:
        _, _, alias_service, supplier_id = self._bootstrap_services()

        alias_service.create_mapping(
            supplier_id=supplier_id,
            alias='opravy',
            canonical_title='Canonical Opravy',
        )

        mapping = alias_service.list_mappings(supplier_id)[0]
        self.assertTrue(alias_service.deactivate_mapping(mapping.id, supplier_id))

        all_entries = alias_service.list_mappings(supplier_id, include_inactive=True)
        self.assertEqual(len(all_entries), 1)
        self.assertEqual(all_entries[0].alias, 'opravy')
        self.assertEqual(all_entries[0].is_active, 0)


if __name__ == '__main__':
    unittest.main()
