from __future__ import annotations

import binascii
import lzma
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class PayBySquareValidationError(ValueError):
    """Raised when PAY by square payment payload contains invalid data."""


_CURRENCY_RE = re.compile(r'^[A-Z]{3}$')
_SYMBOL_RE = re.compile(r'^\d{1,10}$')
_IBAN_RE = re.compile(r'^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$')
_SUBST_TABLE = '0123456789ABCDEFGHIJKLMNOPQRSTUV'


@dataclass(frozen=True)
class PayBySquarePayment:
    iban: str
    amount: Decimal
    currency: str
    variable_symbol: str
    due_date: str
    beneficiary_name: str
    payment_note: str = ''
    swift: str = ''


def _normalize_amount(value: Decimal | float | int | str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PayBySquareValidationError('Amount must be a valid decimal value.') from exc

    if amount <= 0:
        raise PayBySquareValidationError('Amount must be positive.')

    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _validate_iban(iban: str) -> str:
    normalized = iban.replace(' ', '').upper().strip()
    if not _IBAN_RE.match(normalized):
        raise PayBySquareValidationError('IBAN must be uppercase alphanumeric in a valid basic format.')

    rearranged = normalized[4:] + normalized[:4]
    converted = ''.join(str(int(ch, 36)) if ch.isalpha() else ch for ch in rearranged)
    if int(converted) % 97 != 1:
        raise PayBySquareValidationError('IBAN checksum is invalid.')

    return normalized


def _validate_currency(currency: str) -> str:
    normalized = currency.strip().upper()
    if not _CURRENCY_RE.match(normalized):
        raise PayBySquareValidationError('Currency must match ISO 4217 3-letter uppercase code.')
    return normalized


def _validate_variable_symbol(symbol: str) -> str:
    normalized = symbol.strip()
    if not _SYMBOL_RE.match(normalized):
        raise PayBySquareValidationError('Variable symbol must be numeric and up to 10 digits.')
    return normalized


def _validate_due_date(value: str) -> str:
    normalized = value.strip()
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise PayBySquareValidationError('Due date must be a valid ISO date in YYYY-MM-DD format.') from exc
    return parsed.strftime('%Y%m%d')


def _validate_beneficiary_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise PayBySquareValidationError('Beneficiary name is required and cannot be empty.')
    return normalized


def _build_payment_data(payment: PayBySquarePayment) -> bytes:
    iban = _validate_iban(payment.iban)
    amount = _normalize_amount(payment.amount)
    currency = _validate_currency(payment.currency)
    variable_symbol = _validate_variable_symbol(payment.variable_symbol)
    due_date = _validate_due_date(payment.due_date)
    beneficiary_name = _validate_beneficiary_name(payment.beneficiary_name)
    swift = payment.swift.strip().upper()
    note = payment.payment_note.strip()

    data = '\t'.join(
        [
            '',
            '1',  # payment
            '1',  # simple payment
            f'{amount:.2f}',
            currency,
            due_date,
            variable_symbol,
            '',  # constant symbol
            '',  # specific symbol
            '',  # previous 3 entries in SEPA format, empty because already provided above
            note,
            '1',  # to an account
            iban,
            swift,
            '0',  # not recurring
            '0',  # not inkaso
            beneficiary_name,
            '',  # beneficiary address 1
            '',  # beneficiary address 2
        ]
    )

    checksum = binascii.crc32(data.encode('utf-8')).to_bytes(4, 'little')
    return checksum + data.encode('utf-8')


def build_pay_by_square_payload(payment: PayBySquarePayment) -> str:
    total = _build_payment_data(payment)
    compressed = lzma.compress(
        total,
        format=lzma.FORMAT_RAW,
        filters=[
            {
                'id': lzma.FILTER_LZMA1,
                'lc': 3,
                'lp': 0,
                'pb': 2,
                'dict_size': 128 * 1024,
            }
        ],
    )

    payload_bytes = b'\x00\x00' + len(total).to_bytes(2, 'little') + compressed
    bits = ''.join(format(byte, '08b') for byte in payload_bytes)
    remainder = len(bits) % 5
    if remainder:
        bits += '0' * (5 - remainder)

    return ''.join(_SUBST_TABLE[int(bits[i : i + 5], 2)] for i in range(0, len(bits), 5))
