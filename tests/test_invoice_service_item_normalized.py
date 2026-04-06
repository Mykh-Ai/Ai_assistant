from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoicePayload, InvoiceService


class InvoiceServiceItemNormalizedTests(unittest.TestCase):
    def test_create_invoice_persists_normalized_item_title(self) -> None:
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / 'bot.db'
            init_db(db_path)
            service = InvoiceService(db_path)

            invoice_id = service.create_invoice_with_one_item(
                CreateInvoicePayload(
                    supplier_telegram_id=123,
                    contact_id=456,
                    issue_date='2026-04-06',
                    delivery_date='2026-04-06',
                    due_date='2026-04-20',
                    due_days=14,
                    total_amount=120.0,
                    currency='EUR',
                    status='draft_pdf_ready',
                    item_description_raw='web audit',
                    item_description_normalized='Web audit + report',
                    item_quantity=1.0,
                    item_unit='ks',
                    item_unit_price=120.0,
                    item_total_price=120.0,
                )
            )

            items = service.get_items_by_invoice_id(invoice_id)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].description_raw, 'web audit')
            self.assertEqual(items[0].description_normalized, 'Web audit + report')


if __name__ == '__main__':
    unittest.main()
