from __future__ import annotations

import re


def validate_ico(value: str) -> bool:
    return bool(re.fullmatch(r'\d{8}', value.strip()))


def validate_dic(value: str) -> bool:
    return bool(re.fullmatch(r'\d{10}', value.strip()))


def validate_ic_dph(value: str) -> bool:
    normalized = value.strip().upper().replace(' ', '')
    return bool(re.fullmatch(r'[A-Z]{2}\d{8,12}', normalized))


def validate_email(value: str) -> bool:
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', value.strip()))


def validate_iban(value: str) -> bool:
    normalized = value.strip().upper().replace(' ', '')
    return bool(re.fullmatch(r'[A-Z]{2}[0-9A-Z]{13,32}', normalized))


def validate_days_due(value: str) -> bool:
    if not value.strip().isdigit():
        return False
    return int(value.strip()) > 0
