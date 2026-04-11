from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bot.handlers.invoice import _resolve_service_display_name
from bot.services.db import init_db
from bot.services.service_alias_service import ServiceAliasService


class InvoiceServiceDisplayResolutionTests(unittest.TestCase):
    def test_resolves_via_canonical_bridge_when_raw_alias_missing(self) -> None:
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'bot.db'
            init_db(db_path)
            alias_service = ServiceAliasService(db_path)
            alias_service.create_mapping(1, 'opravy', 'Opravy zariadení a servisné práce')

            resolved = _resolve_service_display_name(
                alias_service=alias_service,
                supplier_id=1,
                service_short_name='ремонт',
                service_term_internal='oprava',
            )

            self.assertEqual(resolved, 'Opravy zariadení a servisné práce')

    def test_raw_alias_has_priority_over_canonical_fallback(self) -> None:
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'bot.db'
            init_db(db_path)
            alias_service = ServiceAliasService(db_path)
            alias_service.create_mapping(1, 'ремонт', 'Priamy alias pre ремонт')
            alias_service.create_mapping(1, 'opravy', 'Fallback cez opravy')

            resolved = _resolve_service_display_name(
                alias_service=alias_service,
                supplier_id=1,
                service_short_name='ремонт',
                service_term_internal='oprava',
            )

            self.assertEqual(resolved, 'Priamy alias pre ремонт')

    def test_falls_back_to_raw_name_when_no_alias_match(self) -> None:
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'bot.db'
            init_db(db_path)
            alias_service = ServiceAliasService(db_path)

            resolved = _resolve_service_display_name(
                alias_service=alias_service,
                supplier_id=1,
                service_short_name='ремонт',
                service_term_internal='oprava',
            )

            self.assertEqual(resolved, 'ремонт')


if __name__ == '__main__':
    unittest.main()
