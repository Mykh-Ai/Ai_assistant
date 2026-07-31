from decimal import Decimal
import unittest

import pytest

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


@pytest.mark.unit
@pytest.mark.parametrize(
    'payment',
    [
        pytest.param(
            PayBySquarePayment(
                iban='INVALID',
                amount=Decimal('10.00'),
                currency='EUR',
                variable_symbol='123',
                due_date='2026-04-30',
                beneficiary_name='Supplier',
            ),
            id='invalid-iban',
        ),
        pytest.param(
            PayBySquarePayment(
                iban='SK7700000000000000000000',
                amount=Decimal('10.00'),
                currency='EURO',
                variable_symbol='123',
                due_date='2026-04-30',
                beneficiary_name='Supplier',
            ),
            id='invalid-currency',
        ),
        pytest.param(
            PayBySquarePayment(
                iban='SK7700000000000000000000',
                amount=Decimal('10.00'),
                currency='EUR',
                variable_symbol='ABC123',
                due_date='2026-04-30',
                beneficiary_name='Supplier',
            ),
            id='invalid-variable-symbol',
        ),
        pytest.param(
            PayBySquarePayment(
                iban='SK7700000000000000000000',
                amount=Decimal('10.00'),
                currency='EUR',
                variable_symbol='123',
                due_date='2026-04-30',
                beneficiary_name='   ',
            ),
            id='empty-beneficiary-name',
        ),
        pytest.param(
            PayBySquarePayment(
                iban='SK7700000000000000000000',
                amount=Decimal('0'),
                currency='EUR',
                variable_symbol='123',
                due_date='2026-04-30',
                beneficiary_name='Supplier',
            ),
            id='invalid-amount',
        ),
    ],
)
def test_invalid_payment_field_raises(payment: PayBySquarePayment) -> None:
    with pytest.raises(PayBySquareValidationError):
        build_pay_by_square_payload(payment)


if __name__ == '__main__':
    unittest.main()
