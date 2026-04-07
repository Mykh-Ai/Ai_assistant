from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest
from unittest.mock import patch

from bot.services.contact_service import ContactProfile
from bot.services.supplier_service import SupplierProfile


HAS_PDF_DEPS = importlib.util.find_spec('reportlab') is not None and importlib.util.find_spec('qrcode') is not None


@unittest.skipUnless(HAS_PDF_DEPS, 'reportlab/qrcode are not available in this environment')
class PdfGeneratorPayBySquareSmokeTests(unittest.TestCase):
    def test_pdf_generation_uses_encoded_payload_and_still_writes_pdf(self) -> None:
        from bot.services.pdf_generator import PdfInvoiceData, PdfInvoiceItem, generate_invoice_pdf

        supplier = SupplierProfile(
            telegram_id=1,
            name='Dodávateľ s.r.o.',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='mestská časť Rača, Bratislava 1',
            iban='SK7700000000000000000000',
            swift='FIOZSKBAXXX',
            email='supplier@example.com',
            smtp_host='smtp.example.com',
            smtp_user='user',
            smtp_pass='pass',
            days_due=14,
        )
        customer = ContactProfile(
            supplier_telegram_id=1,
            name='Odberateľ s.r.o.',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='mestská časť Rača, Košice 2',
            email='customer@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
        invoice = PdfInvoiceData(
            invoice_number='20260001',
            issue_date='2026-04-01',
            delivery_date='2026-04-01',
            due_date='2026-04-15',
            variable_symbol='20260001',
            payment_method='bankový prevod',
            total_amount=125.50,
            currency='EUR',
        )
        items = [
            PdfInvoiceItem(
                description='Služby',
                quantity=1.0,
                unit='ks',
                unit_price=125.50,
                total_price=125.50,
            )
        ]

        with TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / 'invoice.pdf'
            with patch('bot.services.pdf_generator._draw_qr') as draw_qr_mock:
                generate_invoice_pdf(
                    target_path=target,
                    supplier=supplier,
                    customer=customer,
                    invoice=invoice,
                    items=items,
                )

            self.assertTrue(target.exists())
            self.assertGreater(target.stat().st_size, 0)

            payload = draw_qr_mock.call_args.args[1]
            self.assertTrue(payload)
            self.assertNotIn('PAYBYSQUARE|IBAN=', payload)
            self.assertRegex(payload, r'^[0-9A-V]+$')


if __name__ == '__main__':
    unittest.main()
