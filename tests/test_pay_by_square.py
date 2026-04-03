from decimal import Decimal
import unittest

from bot.services.pay_by_square import (
    PayBySquarePayment,
    PayBySquareValidationError,
    build_pay_by_square_payload,
)


class PayBySquareTests(unittest.TestCase):
    def _valid_payment(self) -> PayBySquarePayment:
        return PayBySquarePayment(
            iban='SK7700000000000000000000',
            amount=Decimal('123.45'),
            currency='EUR',
            variable_symbol='20260001',
            due_date='2026-04-30',
            beneficiary_name='Test Supplier s.r.o.',
            payment_note='Faktura 20260001',
            swift='FIOZSKBAXXX',
        )

    def test_build_payload_is_deterministic(self) -> None:
        payment = self._valid_payment()
        payload = build_pay_by_square_payload(payment)
        self.assertEqual(
            payload,
            '0007M000BMHL9QQ092PSOB3F1H663SV6BKGN5QFRGQDHET4P9VGS5F84ULCDP3IQKCP6H5VQ8OLTHBDBNNEOQHIAJCHI1IU43PRQ3VP8GCTI34QC9FJ2DE1F48PSEK4C2CK9FE99HVHNKRJMGM49O4LHVVVVVU5F8000',
        )

    def test_invalid_iban_raises(self) -> None:
        with self.assertRaises(PayBySquareValidationError):
            build_pay_by_square_payload(
                PayBySquarePayment(
                    iban='INVALID',
                    amount=Decimal('10.00'),
                    currency='EUR',
                    variable_symbol='123',
                    due_date='2026-04-30',
                    beneficiary_name='Supplier',
                )
            )

    def test_invalid_currency_raises(self) -> None:
        with self.assertRaises(PayBySquareValidationError):
            build_pay_by_square_payload(
                PayBySquarePayment(
                    iban='SK7700000000000000000000',
                    amount=Decimal('10.00'),
                    currency='EURO',
                    variable_symbol='123',
                    due_date='2026-04-30',
                    beneficiary_name='Supplier',
                )
            )

    def test_invalid_variable_symbol_raises(self) -> None:
        with self.assertRaises(PayBySquareValidationError):
            build_pay_by_square_payload(
                PayBySquarePayment(
                    iban='SK7700000000000000000000',
                    amount=Decimal('10.00'),
                    currency='EUR',
                    variable_symbol='ABC123',
                    due_date='2026-04-30',
                    beneficiary_name='Supplier',
                )
            )

    def test_empty_beneficiary_name_raises(self) -> None:
        with self.assertRaises(PayBySquareValidationError):
            build_pay_by_square_payload(
                PayBySquarePayment(
                    iban='SK7700000000000000000000',
                    amount=Decimal('10.00'),
                    currency='EUR',
                    variable_symbol='123',
                    due_date='2026-04-30',
                    beneficiary_name='   ',
                )
            )

    def test_invalid_amount_raises(self) -> None:
        with self.assertRaises(PayBySquareValidationError):
            build_pay_by_square_payload(
                PayBySquarePayment(
                    iban='SK7700000000000000000000',
                    amount=Decimal('0'),
                    currency='EUR',
                    variable_symbol='123',
                    due_date='2026-04-30',
                    beneficiary_name='Supplier',
                )
            )


if __name__ == '__main__':
    unittest.main()
